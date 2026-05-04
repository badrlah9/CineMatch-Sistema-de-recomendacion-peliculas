from __future__ import annotations

"""
Módulo de usuarios similares usando embeddings históricos.

No sustituye al colaborativo principal.
Lo complementa aportando otra señal:
"usuarios parecidos a tu perfil temporal valoraron bien esta película".

Importante:
- esta versión NO usa al usuario actual como usuario conocido del train
- siempre resuelve la consulta desde `user_ratings_df`
"""

from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


class UserBasedEmbeddingsRecommender:
    RESULT_COLUMNS = [
        "movieId",
        "embedding_score",
        "title",
        "genres",
        "rating",
        "num_ratings",
        "neighbor_support",
        "mean_neighbor_similarity",
    ]

    def __init__(
        self,
        collaborative_recommender,
        ratings_df: pd.DataFrame,
        movies_df: pd.DataFrame,
        *,
        min_votes: int = 15,
    ) -> None:
        required_ratings = {"userId", "movieId", "rating"}
        missing_ratings = required_ratings - set(ratings_df.columns)
        if missing_ratings:
            raise ValueError(
                f"ratings_df no tiene columnas necesarias: {sorted(missing_ratings)}"
            )

        required_movies = {"movieId", "title", "genres", "rating", "num_ratings"}
        missing_movies = required_movies - set(movies_df.columns)
        if missing_movies:
            raise ValueError(
                f"movies_df no tiene columnas necesarias: {sorted(missing_movies)}"
            )

        self.rec = collaborative_recommender
        self.ratings_df = ratings_df.copy()
        self.movies_df = movies_df.copy()
        self.min_votes = int(min_votes)

        # Estos embeddings corresponden a usuarios históricos del entrenamiento.
        self.user_embeddings = self.rec.user_embeddings
        self.user_to_index = self.rec.user_to_index
        self.index_to_user = {index: user_id for user_id, index in self.user_to_index.items()}

    def _empty_result(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.RESULT_COLUMNS)

    def _resolve_query_vector(
        self,
        user_ratings_df: Optional[pd.DataFrame] = None,
    ) -> Optional[np.ndarray]:
        """
        Obtiene el vector sobre el que vamos a buscar vecinos.

        En esta versión:
        - siempre se infiere desde ratings del usuario actual
        - nunca se usa `user_id` como embedding directo del train
        """
        if user_ratings_df is None or user_ratings_df.empty:
            return None

        profile = self.rec.infer_user_profile(user_ratings_df)
        if profile is None:
            return None

        return profile.vector.reshape(1, -1)

    def _get_similar_users(
        self,
        user_ratings_df: Optional[pd.DataFrame] = None,
        top_k: int = 40,
        min_similarity: float = 0.10,
    ) -> list[tuple[int | str, float]]:
        """
        Devuelve usuarios históricos más parecidos al perfil temporal actual.
        """
        query_vector = self._resolve_query_vector(user_ratings_df=user_ratings_df)
        if query_vector is None:
            return []

        similarities = cosine_similarity(query_vector, self.user_embeddings)[0]
        candidate_indices = np.argsort(similarities)[::-1]

        results: list[tuple[int | str, float]] = []
        for index in candidate_indices:
            similarity = float(similarities[index])
            if similarity < min_similarity:
                continue

            candidate_user_id = self.index_to_user[index]
            results.append((candidate_user_id, similarity))

            if len(results) >= top_k:
                break

        return results

    def score_candidates(
        self,
        user_id: int | str | None = None,
        seen_movie_ids: Optional[Iterable[int]] = None,
        candidate_ids: Optional[Sequence[int]] = None,
        user_ratings_df: Optional[pd.DataFrame] = None,
        top_k_users: int = 40,
        min_similarity: float = 0.10,
    ) -> pd.DataFrame:
        """
        Puntúa candidatas según usuarios similares en embeddings.

        `user_id` se acepta solo para mantener interfaz uniforme.
        """
        del user_id

        similar_users = self._get_similar_users(
            user_ratings_df=user_ratings_df,
            top_k=top_k_users,
            min_similarity=min_similarity,
        )
        if not similar_users:
            return self._empty_result()

        similarity_by_user = dict(similar_users)
        seen_movie_ids = set(seen_movie_ids or [])

        df = self.ratings_df[
            (self.ratings_df["userId"].isin(similarity_by_user.keys()))
            & (~self.ratings_df["movieId"].isin(seen_movie_ids))
        ].copy()

        if candidate_ids is not None:
            candidate_ids = set(candidate_ids)
            df = df[df["movieId"].isin(candidate_ids)]

        if df.empty:
            return self._empty_result()

        df["similarity"] = df["userId"].map(similarity_by_user).astype(float)

        # Centramos ratings en 3.0 para que lo neutro pese menos.
        df["centered_rating"] = df["rating"].astype(float) - 3.0
        df["weighted"] = df["centered_rating"] * df["similarity"]

        grouped = df.groupby("movieId").agg(
            weighted_sum=("weighted", "sum"),
            similarity_sum=("similarity", "sum"),
            neighbor_support=("userId", "nunique"),
            mean_neighbor_similarity=("similarity", "mean"),
        ).reset_index()

        grouped = grouped[grouped["similarity_sum"] > 0]
        if grouped.empty:
            return self._empty_result()

        # Volvemos a una escala interpretable cercana al rating.
        grouped["embedding_score"] = 3.0 + (
            grouped["weighted_sum"] / grouped["similarity_sum"]
        )
        grouped["embedding_score"] = grouped["embedding_score"].clip(0.5, 5.0)

        grouped = grouped.merge(
            self.movies_df[["movieId", "title", "genres", "rating", "num_ratings"]],
            on="movieId",
            how="left",
        )

        grouped = grouped.dropna(subset=["rating", "num_ratings"])
        if grouped.empty:
            return self._empty_result()

        grouped["rating"] = grouped["rating"].astype(float)
        grouped["num_ratings"] = grouped["num_ratings"].astype(float)

        popularity = np.log1p(grouped["num_ratings"])
        popularity = popularity / popularity.max() if popularity.max() > 0 else 0.0

        # Mezcla suave de:
        # - la señal colaborativa de vecinos
        # - la calidad del catálogo
        # - la popularidad
        grouped["embedding_score"] = (
            grouped["embedding_score"] * 0.72
            + (grouped["rating"] / 5.0) * 0.18
            + popularity * 0.10
        )

        # Regularización ligera: si pocos vecinos la apoyan, baja algo el score.
        grouped["embedding_score"] *= (
            grouped["neighbor_support"] / (grouped["neighbor_support"] + 4.0)
        )

        grouped = grouped[grouped["num_ratings"] >= self.min_votes]
        if grouped.empty:
            return self._empty_result()

        return grouped[self.RESULT_COLUMNS].sort_values(
            "embedding_score",
            ascending=False,
        ).reset_index(drop=True)

    def recommend(
        self,
        user_id: int | str | None = None,
        seen_movie_ids: Optional[Iterable[int]] = None,
        top_n: int = 10,
        user_ratings_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Recomendación pura basada en vecinos.
        """
        del user_id

        if top_n <= 0:
            return self._empty_result()

        df = self.score_candidates(
            user_id=None,
            seen_movie_ids=seen_movie_ids,
            candidate_ids=None,
            user_ratings_df=user_ratings_df,
        )
        if df.empty:
            return self._empty_result()

        return df.head(top_n).reset_index(drop=True)
