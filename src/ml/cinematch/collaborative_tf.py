from __future__ import annotations

"""
Recomendador colaborativo en TensorFlow / Keras.

Puntos clave de esta versión:
- usa tu modelo ya entrenado en Keras
- trata a los usuarios de producto como externos a MovieLens
- NO usa `user_id` para tirar de embeddings de usuario del train
- sí usa los patrones del train para:
  - embeddings de películas
  - embeddings de usuarios históricos
  - vecinos similares
- la señal colaborativa se obtiene inferiendo un perfil temporal
  a partir de los ratings reales del usuario actual
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
from tensorflow import keras

from cinematch.io_utils import load_json, load_pickle


REQUIRED_MOVIE_COLUMNS = {"movieId", "title", "genres", "rating", "num_ratings"}


@keras.utils.register_keras_serializable(package="CineMatch")
class MatrixFactorizationModel(keras.Model):
    """
    Definición compatible con el modelo guardado durante el entrenamiento.

    Se incluye aquí para poder cargar correctamente `.keras` cuando el modelo
    fue guardado como clase custom subclassed.
    """

    def __init__(
        self,
        num_users: int,
        num_movies: int,
        embedding_dim: int,
        global_mean: float,
        l2_embeddings: float = 1e-6,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self.num_users = int(num_users)
        self.num_movies = int(num_movies)
        self.embedding_dim = int(embedding_dim)
        self.global_mean_value = float(global_mean)
        self.l2_embeddings = float(l2_embeddings)

        regularizer = keras.regularizers.l2(self.l2_embeddings)
        self.global_mean = keras.ops.convert_to_tensor(self.global_mean_value, dtype="float32")

        self.user_embedding = keras.layers.Embedding(
            input_dim=self.num_users,
            output_dim=self.embedding_dim,
            embeddings_initializer="he_normal",
            embeddings_regularizer=regularizer,
            name="user_embedding",
        )
        self.movie_embedding = keras.layers.Embedding(
            input_dim=self.num_movies,
            output_dim=self.embedding_dim,
            embeddings_initializer="he_normal",
            embeddings_regularizer=regularizer,
            name="movie_embedding",
        )
        self.user_bias = keras.layers.Embedding(
            input_dim=self.num_users,
            output_dim=1,
            embeddings_initializer="zeros",
            embeddings_regularizer=regularizer,
            name="user_bias",
        )
        self.movie_bias = keras.layers.Embedding(
            input_dim=self.num_movies,
            output_dim=1,
            embeddings_initializer="zeros",
            embeddings_regularizer=regularizer,
            name="movie_bias",
        )

        self.dot = keras.layers.Dot(axes=1, name="dot_product")
        self.add = keras.layers.Add(name="sum_scores")

    def call(self, inputs, training: bool = False):
        user_ids, movie_ids = inputs

        user_vector = self.user_embedding(user_ids)
        movie_vector = self.movie_embedding(movie_ids)

        user_bias = self.user_bias(user_ids)
        movie_bias = self.movie_bias(movie_ids)

        interaction = self.dot([user_vector, movie_vector])
        output = self.add([interaction, user_bias, movie_bias])
        output = keras.ops.cast(output, "float32")
        output = keras.ops.squeeze(output, axis=-1) + self.global_mean

        return output

    def get_config(self) -> dict:
        config = super().get_config()
        config.update(
            {
                "num_users": self.num_users,
                "num_movies": self.num_movies,
                "embedding_dim": self.embedding_dim,
                "global_mean": self.global_mean_value,
                "l2_embeddings": self.l2_embeddings,
            }
        )
        return config

    @classmethod
    def from_config(cls, config: dict):
        return cls(**config)


@dataclass
class InferredUserProfile:
    """
    Perfil colaborativo inferido para un usuario externo al entrenamiento.

    vector:
        Vector temporal del usuario en el mismo espacio que las películas.
    bias:
        Sesgo aproximado del usuario respecto a la media global.
    support:
        Número de ratings válidos usados para construir el perfil.
    mean_rating:
        Rating medio del usuario sobre las películas conocidas por el modelo.
    seen_movie_ids:
        Películas ya puntuadas por el usuario.
    """

    vector: np.ndarray
    bias: float
    support: int
    mean_rating: float
    seen_movie_ids: set[int]


class TensorFlowCollaborativeRecommender:
    """
    Recomendador colaborativo principal.

    Regla de negocio importante:
    - los usuarios reales del producto se consideran externos al entrenamiento
    - por tanto, esta clase NO recomienda usando embeddings directos por `user_id`
    - la colaboración sale siempre del perfil temporal inferido desde `user_ratings_df`
    """

    RESULT_COLUMNS = [
        "movieId",
        "svd_score",
        "title",
        "genres",
        "rating",
        "num_ratings",
    ]

    def __init__(
        self,
        model_path: str,
        mappings_path: str,
        metadata_path: Optional[str] = None,
    ) -> None:
        self.mappings = load_pickle(Path(mappings_path))
        self.metadata = load_json(Path(metadata_path)) if metadata_path else {}

        self.user_to_index = self.mappings["user_to_index"]
        self.movie_to_index = self.mappings["movie_to_index"]
        self.embedding_dim = int(self.mappings["embedding_dim"])
        self.global_mean = float(self.mappings.get("global_mean", 3.5))
        self.rating_min = float(self.mappings.get("rating_min", 0.5))
        self.rating_max = float(self.mappings.get("rating_max", 5.0))

        self.model = keras.models.load_model(
            model_path,
            compile=False,
            custom_objects={"MatrixFactorizationModel": MatrixFactorizationModel},
        )

        # Extraemos pesos una vez para usarlos rápido en numpy.
        self.user_embeddings = self.model.get_layer("user_embedding").get_weights()[0]
        self.movie_embeddings = self.model.get_layer("movie_embedding").get_weights()[0]
        self.user_biases = self.model.get_layer("user_bias").get_weights()[0].reshape(-1)
        self.movie_biases = self.model.get_layer("movie_bias").get_weights()[0].reshape(-1)

    def _validate_movies_df(self, movies_df: pd.DataFrame) -> None:
        missing = REQUIRED_MOVIE_COLUMNS - set(movies_df.columns)
        if missing:
            raise ValueError(
                f"movies_df no tiene columnas necesarias: {sorted(missing)}"
            )

    def _empty_result(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.RESULT_COLUMNS)

    @staticmethod
    def _safe_unit_vector(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        if norm == 0.0 or np.isnan(norm):
            return vector
        return vector / norm

    def available_movie_ids(self) -> set[int]:
        """
        Devuelve el catálogo de movieIds que el modelo conoce.
        """
        return set(self.movie_to_index.keys())

    @property
    def external_user_only(self) -> bool:
        """
        Señal explícita para dejar claro que esta versión nunca usa el usuario
        como "conocido del train" aunque casualmente el ID coincidiera.
        """
        return True

    def infer_user_profile(
        self,
        user_ratings_df: Optional[pd.DataFrame],
    ) -> Optional[InferredUserProfile]:
        """
        Infiere un perfil temporal desde ratings reales del usuario actual.

        Estrategia:
        1. filtra películas conocidas por el modelo
        2. construye un vector combinando embeddings de las películas puntuadas
        3. pondera más los ratings alejados del neutro (3.0)
        4. estima un sesgo sencillo del usuario
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

        df["movieId"] = df["movieId"].astype(int)
        df["rating"] = df["rating"].astype(float).clip(self.rating_min, self.rating_max)

        # Solo podemos usar películas presentes en el entrenamiento.
        df = df[df["movieId"].isin(self.movie_to_index)]
        if df.empty:
            return None

        movie_ids = df["movieId"].tolist()
        ratings = df["rating"].to_numpy(dtype=float)

        movie_indices = np.array(
            [self.movie_to_index[movie_id] for movie_id in movie_ids],
            dtype=np.int32,
        )

        movie_vectors = self.movie_embeddings[movie_indices]
        movie_biases = self.movie_biases[movie_indices]

        # El rating neutro es 3.0. Ratings por encima / debajo generan dirección.
        centered = (ratings - 3.0) / 2.0  # aprox. [-1, 1]
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

        # Sesgo aproximado del usuario: rating - media global - bias de película.
        user_bias = float(np.mean(ratings - self.global_mean - movie_biases))

        return InferredUserProfile(
            vector=user_vector,
            bias=user_bias,
            support=int(len(df)),
            mean_rating=float(np.mean(ratings)),
            seen_movie_ids=set(movie_ids),
        )

    def score_candidates_from_profile(
        self,
        profile: Optional[InferredUserProfile],
        candidate_ids: Sequence[int],
        movies_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Puntúa candidatas usando el perfil temporal inferido.
        """
        self._validate_movies_df(movies_df)

        if profile is None or not candidate_ids:
            return self._empty_result()

        valid_ids = [movie_id for movie_id in candidate_ids if movie_id in self.movie_to_index]
        if not valid_ids:
            return self._empty_result()

        movie_indices = np.array(
            [self.movie_to_index[movie_id] for movie_id in valid_ids],
            dtype=np.int32,
        )

        movie_vectors = self.movie_embeddings[movie_indices]
        movie_biases = self.movie_biases[movie_indices]

        raw_scores = (
            movie_vectors @ profile.vector
            + movie_biases
            + profile.bias
            + self.global_mean
        )

        predictions = np.clip(raw_scores.astype(float), self.rating_min, self.rating_max)

        df = pd.DataFrame({"movieId": valid_ids, "svd_score": predictions})
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

        `user_id` se acepta para mantener interfaz homogénea con el resto del
        proyecto, pero se ignora deliberadamente para no usar nunca al usuario
        como "usuario conocido del train".

        Si no hay `user_ratings_df`, se devuelve vacío y el híbrido caerá a
        contenido puro o a la señal que sí esté disponible.
        """
        del user_id  # explícito: esta versión no usa user_id para inferencia

        self._validate_movies_df(movies_df)

        if user_ratings_df is None or user_ratings_df.empty:
            return self._empty_result()

        profile = self.infer_user_profile(user_ratings_df)
        if profile is None:
            return self._empty_result()

        return self.score_candidates_from_profile(
            profile=profile,
            candidate_ids=candidate_ids,
            movies_df=movies_df,
        )

    def recommend(
        self,
        user_id: int | str | None,
        seen_movie_ids: Optional[Iterable[int]],
        movies_df: pd.DataFrame,
        top_n: int = 10,
        user_ratings_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Recomendación colaborativa pura para usuario externo.

        El `user_id` no se usa para recomendar, solo se acepta por consistencia
        con el resto de interfaces del proyecto.
        """
        del user_id

        if top_n <= 0:
            return self._empty_result()

        seen_ids = set(seen_movie_ids or [])
        candidate_ids = [
            movie_id
            for movie_id in movies_df["movieId"].astype(int).tolist()
            if movie_id not in seen_ids
        ]

        if not candidate_ids:
            return self._empty_result()

        df = self.score_candidates(
            user_id=None,
            candidate_ids=candidate_ids,
            movies_df=movies_df,
            user_ratings_df=user_ratings_df,
        )
        return df.head(top_n).reset_index(drop=True)
