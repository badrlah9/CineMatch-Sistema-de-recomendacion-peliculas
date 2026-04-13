
"""
Recomendador de usuarios similares apoyado en embeddings.

Diferencia clave respecto a la versión anterior:
- ya no depende de que `user_id` exista en el entrenamiento
- puede apoyarse en un perfil temporal inferido a partir de ratings reales
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


class UserBasedEmbeddingsRecommender:
    """
    Busca usuarios históricos parecidos en el espacio de embeddings
    y agrega películas que esos usuarios valoraron bien.
    """

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
        svd_recommender,
        ratings_df: pd.DataFrame,
        movies_df: pd.DataFrame,
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

        self.rec = svd_recommender
        self.ratings_df = ratings_df.copy()
        self.movies_df = movies_df.copy()

        self.user_embeddings = self.rec.model.user_embedding.weight.detach().cpu().numpy()
        self.user_to_index = self.rec.user_to_index
        self.index_to_user = {v: k for k, v in self.user_to_index.items()}

    def _empty_result(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.RESULT_COLUMNS)

    def _resolve_query_vector(
        self,
        user_id: int | str | None = None,
        user_ratings_df: Optional[pd.DataFrame] = None,
    ) -> Optional[np.ndarray]:
        """
        Devuelve el vector del usuario sobre el que vamos a buscar vecinos.
        """
        if user_ratings_df is not None and not user_ratings_df.empty:
            profile = self.rec.infer_user_profile(user_ratings_df)
            if profile is not None:
                return profile.vector.reshape(1, -1)

        if user_id in self.user_to_index:
            user_idx = self.user_to_index[user_id]
            return self.user_embeddings[user_idx].reshape(1, -1)

        return None

    def _get_similar_users(
        self,
        user_id: int | str | None = None,
        user_ratings_df: Optional[pd.DataFrame] = None,
        top_k: int = 40,
        min_similarity: float = 0.10,
    ) -> list[tuple[int | str, float]]:
        """
        Obtiene usuarios históricos más parecidos.
        """
        query_vector = self._resolve_query_vector(
            user_id=user_id,
            user_ratings_df=user_ratings_df,
        )
        if query_vector is None:
            return []

        sims = cosine_similarity(query_vector, self.user_embeddings)[0]
        similar_indices = np.argsort(sims)[::-1]

        results: list[tuple[int | str, float]] = []
        for idx in similar_indices:
            sim = float(sims[idx])

            if sim < min_similarity:
                continue

            user_candidate = self.index_to_user[idx]

            # Si el query user es histórico, evitamos devolverse a sí mismo.
            if user_id in self.user_to_index and user_candidate == user_id:
                continue

            results.append((user_candidate, sim))

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
        """
        similar_users = self._get_similar_users(
            user_id=user_id,
            user_ratings_df=user_ratings_df,
            top_k=top_k_users,
            min_similarity=min_similarity,
        )
        if not similar_users:
            return self._empty_result()

        sim_dict = dict(similar_users)
        seen_movie_ids = set(seen_movie_ids or [])

        df = self.ratings_df[
            (self.ratings_df["userId"].isin(sim_dict.keys()))
            & (~self.ratings_df["movieId"].isin(seen_movie_ids))
        ].copy()

        if candidate_ids is not None:
            candidate_ids = set(candidate_ids)
            df = df[df["movieId"].isin(candidate_ids)]

        if df.empty:
            return self._empty_result()

        df["sim"] = df["userId"].map(sim_dict).astype(float)

        # Centrar ratings en 3.0 ayuda a que los muy neutrales pesen menos.
        df["centered_rating"] = df["rating"].astype(float) - 3.0
        df["weighted"] = df["centered_rating"] * df["sim"]

        grouped = df.groupby("movieId").agg(
            weighted_sum=("weighted", "sum"),
            sim_sum=("sim", "sum"),
            neighbor_support=("userId", "nunique"),
            mean_neighbor_similarity=("sim", "mean"),
        ).reset_index()

        grouped = grouped[grouped["sim_sum"] > 0]
        if grouped.empty:
            return self._empty_result()

        # Volvemos a escala interpretable.
        grouped["embedding_score"] = 3.0 + (
            grouped["weighted_sum"] / grouped["sim_sum"]
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

        grouped["embedding_score"] = (
            grouped["embedding_score"] * 0.72
            + (grouped["rating"] / 5.0) * 0.18
            + popularity * 0.10
        )

        grouped["embedding_score"] *= (
            grouped["neighbor_support"] / (grouped["neighbor_support"] + 4.0)
        )

        grouped = grouped[grouped["num_ratings"] >= 15]
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
        Recomendación pura basada en vecinos en embeddings.
        """
        if top_n <= 0:
            return self._empty_result()

        grouped = self.score_candidates(
            user_id=user_id,
            seen_movie_ids=seen_movie_ids,
            candidate_ids=None,
            user_ratings_df=user_ratings_df,
        )

        if grouped.empty:
            return self._empty_result()

        return grouped.head(top_n).reset_index(drop=True)
