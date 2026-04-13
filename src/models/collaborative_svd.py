
"""
Módulo colaborativo basado en embeddings SVD.

Objetivo del refactor
---------------------
Este fichero deja de depender exclusivamente de que el `user_id` exista
en la base original de entrenamiento. Ahora también puede inferir un
perfil colaborativo temporal a partir de los ratings del usuario actual.

Eso permite:
- usar colaborativo con usuarios externos a MovieLens
- puntuar candidatas usando embeddings de películas
- servir de base al orquestador híbrido
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
import torch


# ============================================================
# MODELO SVD CON EMBEDDINGS
# ============================================================


class SVDModel(torch.nn.Module):
    """Modelo de factorización matricial con embeddings y sesgos."""

    def __init__(self, num_users: int, num_movies: int, embedding_dim: int) -> None:
        super().__init__()
        self.user_embedding = torch.nn.Embedding(num_users, embedding_dim)
        self.movie_embedding = torch.nn.Embedding(num_movies, embedding_dim)
        self.user_bias = torch.nn.Embedding(num_users, 1)
        self.movie_bias = torch.nn.Embedding(num_movies, 1)

    def forward(self, users: torch.Tensor, movies: torch.Tensor) -> torch.Tensor:
        user_vec = self.user_embedding(users)
        movie_vec = self.movie_embedding(movies)

        interaction = (user_vec * movie_vec).sum(dim=1)
        user_b = self.user_bias(users).squeeze(1)
        movie_b = self.movie_bias(movies).squeeze(1)

        return interaction + user_b + movie_b


# ============================================================
# PERFIL COLABORATIVO TEMPORAL
# ============================================================


@dataclass
class InferredUserProfile:
    """
    Perfil colaborativo inferido para un usuario externo al entrenamiento.

    Attributes
    ----------
    vector:
        Vector latente del usuario en el mismo espacio de embeddings que el SVD.
    bias:
        Sesgo aproximado del usuario respecto a la media global.
    support:
        Número de ratings útiles para construir el perfil.
    mean_rating:
        Rating medio del usuario sobre las películas válidas.
    seen_movie_ids:
        Películas ya valoradas por el usuario.
    """

    vector: np.ndarray
    bias: float
    support: int
    mean_rating: float
    seen_movie_ids: set[int]


# ============================================================
# RECOMENDADOR COLABORATIVO
# ============================================================


class Recommender:
    """
    Recomendador colaborativo SVD.

    Mejoras respecto a la versión original:
    - puede puntuar usuarios conocidos del entrenamiento
    - puede inferir un perfil colaborativo temporal para usuarios externos
    - añade validaciones y manejo defensivo de errores
    """

    REQUIRED_MOVIE_COLUMNS = {"movieId", "title", "genres", "rating", "num_ratings"}
    RESULT_COLUMNS = [
        "movieId",
        "svd_score",
        "title",
        "genres",
        "rating",
        "num_ratings",
    ]

    def __init__(self, model_path: str, device: Optional[str] = None) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        checkpoint = torch.load(
            model_path,
            map_location=self.device,
            weights_only=False,
        )

        self.user_to_index = checkpoint["user_to_index"]
        self.movie_to_index = checkpoint["movie_to_index"]
        self.global_mean = float(checkpoint["global_mean"])
        self.embedding_dim = int(checkpoint["embedding_dim"])

        self.model = SVDModel(
            num_users=len(self.user_to_index),
            num_movies=len(self.movie_to_index),
            embedding_dim=self.embedding_dim,
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

        # Cacheamos pesos en CPU para trabajar rápido con numpy.
        self._user_embeddings = self.model.user_embedding.weight.detach().cpu().numpy()
        self._movie_embeddings = self.model.movie_embedding.weight.detach().cpu().numpy()
        self._movie_biases = (
            self.model.movie_bias.weight.detach().cpu().numpy().reshape(-1)
        )
        self._user_biases = (
            self.model.user_bias.weight.detach().cpu().numpy().reshape(-1)
        )

    # --------------------------------------------------------
    # Utilidades internas
    # --------------------------------------------------------

    def _validate_movies_df(self, movies_df: pd.DataFrame) -> None:
        missing = self.REQUIRED_MOVIE_COLUMNS - set(movies_df.columns)
        if missing:
            raise ValueError(
                f"movies_df no tiene columnas necesarias: {sorted(missing)}"
            )

    def _empty_result(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.RESULT_COLUMNS)

    def has_trained_user(self, user_id: int | str | None) -> bool:
        """Indica si el usuario existía en el entrenamiento original."""
        return user_id in self.user_to_index if user_id is not None else False

    def available_movie_ids(self) -> set[int]:
        """Devuelve el conjunto de películas conocidas por el modelo."""
        return set(self.movie_to_index.keys())

    @staticmethod
    def _clip_ratings(values: np.ndarray) -> np.ndarray:
        return np.clip(values.astype(float), 0.5, 5.0)

    @staticmethod
    def _safe_unit_vector(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        if norm == 0.0 or np.isnan(norm):
            return vector
        return vector / norm

    def _scale_raw_scores(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Escala scores latentes a rango aproximado 0.5 - 5.0.

        El SVD produce una señal no acotada; esta función la lleva a un rango
        interpretable sin cortar bruscamente la distribución.
        """
        shifted = raw_scores - self.global_mean
        return 0.5 + 4.5 / (1.0 + np.exp(-shifted))

    # --------------------------------------------------------
    # Perfil temporal para usuarios externos
    # --------------------------------------------------------

    def infer_user_profile(
        self,
        user_ratings_df: Optional[pd.DataFrame],
    ) -> Optional[InferredUserProfile]:
        """
        Infiere un perfil colaborativo temporal usando ratings del usuario.

        Estrategia:
        1. filtra películas conocidas por el modelo
        2. combina embeddings de películas valoradas
        3. pondera más los ratings alejados de 3.0
        4. estima un sesgo de usuario aproximado
        """
        if user_ratings_df is None or user_ratings_df.empty:
            return None

        required = {"movieId", "rating"}
        missing = required - set(user_ratings_df.columns)
        if missing:
            raise ValueError(
                f"user_ratings_df debe tener columnas {sorted(required)}. "
                f"Faltan: {sorted(missing)}"
            )

        df = user_ratings_df.copy()
        df = df.dropna(subset=["movieId", "rating"])

        if df.empty:
            return None

        df = df[df["movieId"].isin(self.movie_to_index)]
        if df.empty:
            return None

        movie_ids = df["movieId"].astype(int).tolist()
        ratings = self._clip_ratings(df["rating"].to_numpy())

        movie_indices = np.array(
            [self.movie_to_index[movie_id] for movie_id in movie_ids],
            dtype=np.int64,
        )
        movie_vectors = self._movie_embeddings[movie_indices]
        movie_biases = self._movie_biases[movie_indices]

        # Señal principal: cuánto se aleja del rating neutro.
        centered = (ratings - 3.0) / 2.0  # rango aprox. [-1, 1]
        confidence = np.abs(centered) + 0.15
        signed_weights = np.sign(centered)
        signed_weights[signed_weights == 0] = 1.0
        preference_weights = confidence * signed_weights

        preference_component = np.average(
            movie_vectors,
            axis=0,
            weights=np.abs(preference_weights),
        )

        directional_component = np.sum(
            movie_vectors * preference_weights.reshape(-1, 1),
            axis=0,
        )

        positive_mask = ratings >= 3.5
        if positive_mask.any():
            positive_component = np.average(
                movie_vectors[positive_mask],
                axis=0,
                weights=np.maximum(ratings[positive_mask] - 3.0, 0.1),
            )
        else:
            positive_component = preference_component

        user_vector = (
            0.45 * preference_component
            + 0.40 * directional_component
            + 0.15 * positive_component
        )
        user_vector = self._safe_unit_vector(user_vector.astype(float))

        # Sesgo aproximado del usuario.
        user_bias = float(np.mean(ratings - self.global_mean - movie_biases))

        return InferredUserProfile(
            vector=user_vector,
            bias=user_bias,
            support=int(len(df)),
            mean_rating=float(np.mean(ratings)),
            seen_movie_ids=set(movie_ids),
        )

    # --------------------------------------------------------
    # Scoring para usuarios del entrenamiento original
    # --------------------------------------------------------

    def predict_batch(
        self,
        user_id: int | str,
        movie_ids: Sequence[int],
        batch_size: int = 65536,
    ) -> tuple[np.ndarray, list[int]]:
        """
        Predice scores SVD para un usuario existente en el entrenamiento.
        """
        if user_id not in self.user_to_index:
            return np.array([]), []

        if not movie_ids:
            return np.array([]), []

        valid_ids = [m for m in movie_ids if m in self.movie_to_index]
        if not valid_ids:
            return np.array([]), []

        user_idx = self.user_to_index[user_id]
        movie_indices = np.array(
            [self.movie_to_index[m] for m in valid_ids],
            dtype=np.int64,
        )
        user_indices = np.full(len(movie_indices), user_idx, dtype=np.int64)

        user_tensor = torch.tensor(user_indices, dtype=torch.long)
        movie_tensor = torch.tensor(movie_indices, dtype=torch.long)

        preds = []
        with torch.no_grad():
            for i in range(0, len(user_tensor), batch_size):
                u_batch = user_tensor[i : i + batch_size].to(self.device)
                m_batch = movie_tensor[i : i + batch_size].to(self.device)
                batch = self.model(u_batch, m_batch) + self.global_mean
                preds.append(batch.cpu())

        raw_scores = torch.cat(preds).numpy()
        scaled_scores = self._scale_raw_scores(raw_scores)
        return scaled_scores, valid_ids

    # --------------------------------------------------------
    # Scoring para usuarios temporales
    # --------------------------------------------------------

    def score_candidates_from_profile(
        self,
        profile: Optional[InferredUserProfile],
        candidate_ids: Sequence[int],
        movies_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Puntúa candidatas usando un perfil temporal inferido.
        """
        self._validate_movies_df(movies_df)

        if profile is None or not candidate_ids:
            return self._empty_result()

        valid_ids = [m for m in candidate_ids if m in self.movie_to_index]
        if not valid_ids:
            return self._empty_result()

        movie_indices = np.array(
            [self.movie_to_index[m] for m in valid_ids],
            dtype=np.int64,
        )

        movie_vectors = self._movie_embeddings[movie_indices]
        movie_biases = self._movie_biases[movie_indices]

        raw_scores = (
            movie_vectors @ profile.vector
            + movie_biases
            + profile.bias
            + self.global_mean
        )
        preds = self._scale_raw_scores(raw_scores)

        df = pd.DataFrame({"movieId": valid_ids, "svd_score": preds})
        df = df.merge(
            movies_df[["movieId", "title", "genres", "rating", "num_ratings"]],
            on="movieId",
            how="left",
        )

        return df.sort_values("svd_score", ascending=False).reset_index(drop=True)

    def score_candidates(
        self,
        user_id: int | str | None,
        candidate_ids: Sequence[int],
        movies_df: pd.DataFrame,
        user_ratings_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Punto único de scoring colaborativo.

        Prioridad:
        1. si llega `user_ratings_df`, se infiere perfil temporal y se usa ese
        2. si no hay ratings pero el usuario existe en entrenamiento, usa SVD clásico
        3. si no se puede puntuar, devuelve vacío
        """
        self._validate_movies_df(movies_df)

        if user_ratings_df is not None and not user_ratings_df.empty:
            profile = self.infer_user_profile(user_ratings_df)
            if profile is not None:
                return self.score_candidates_from_profile(
                    profile=profile,
                    candidate_ids=candidate_ids,
                    movies_df=movies_df,
                )

        preds, valid_ids = self.predict_batch(user_id=user_id, movie_ids=candidate_ids)
        if len(valid_ids) == 0:
            return self._empty_result()

        df = pd.DataFrame({"movieId": valid_ids, "svd_score": preds})
        df = df.merge(
            movies_df[["movieId", "title", "genres", "rating", "num_ratings"]],
            on="movieId",
            how="left",
        )
        return df.sort_values("svd_score", ascending=False).reset_index(drop=True)

    def recommend(
        self,
        user_id: int | str | None,
        seen_movie_ids: Optional[Iterable[int]],
        movies_df: pd.DataFrame,
        top_n: int = 10,
        user_ratings_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Recomendación colaborativa pura.

        Puede funcionar con:
        - usuarios del entrenamiento
        - usuarios externos con ratings propios
        """
        if top_n <= 0:
            return self._empty_result()

        seen_ids = set(seen_movie_ids or [])
        candidate_ids = [
            movie_id
            for movie_id in movies_df["movieId"].tolist()
            if movie_id not in seen_ids
        ]

        if not candidate_ids:
            return self._empty_result()

        df = self.score_candidates(
            user_id=user_id,
            candidate_ids=candidate_ids,
            movies_df=movies_df,
            user_ratings_df=user_ratings_df,
        )
        return df.head(top_n).reset_index(drop=True)
