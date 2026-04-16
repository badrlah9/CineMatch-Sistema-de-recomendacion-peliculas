from __future__ import annotations

"""
Orquestador central del sistema híbrido.

Este módulo decide:
- cuándo usar contenido puro
- cuándo activar colaborativo temporal
- cuándo sumar vecinos similares
- cómo mezclar las señales
- cómo rotar resultados sin romper la coherencia

Regla principal de esta versión:
- los usuarios de tu producto se tratan siempre como externos al train
- el `user_id` solo sirve para trazabilidad y estado de rotación
- la colaboración sale de `user_ratings_df`
"""

import hashlib
import json
from copy import deepcopy
from typing import Mapping, Optional

import pandas as pd

from cinematch.collaborative_tf import TensorFlowCollaborativeRecommender
from cinematch.content_based import (
    compute_baseline_scores,
    normalize_genres,
    normalize_user_preferences,
)
from cinematch.neighbor_embeddings import UserBasedEmbeddingsRecommender


class HybridOrchestrator:
    REQUIRED_MOVIE_COLUMNS = {"movieId", "title", "genres", "rating", "num_ratings"}
    EMPTY_COLUMNS = [
        "movieId",
        "title",
        "genres",
        "rating",
        "num_ratings",
        "baseline_score",
        "svd_score",
        "embedding_score",
        "final_score",
        "rotated_score",
        "rotation_penalty",
        "rotation_jitter",
        "genre_score",
        "rating_score",
        "popularity_score",
    ]

    def __init__(
        self,
        collaborative_recommender: TensorFlowCollaborativeRecommender,
        ratings_df: pd.DataFrame,
        movies_df: pd.DataFrame,
        *,
        memory_decay: float = 0.80,
        max_history_signatures: int = 200,
        min_catalog_votes: int = 10,
        min_neighbor_votes: int = 15,
    ) -> None:
        missing = self.REQUIRED_MOVIE_COLUMNS - set(movies_df.columns)
        if missing:
            raise ValueError(
                f"movies_df no tiene columnas necesarias: {sorted(missing)}"
            )

        self.ratings_df = ratings_df.copy()
        self.movies_df = movies_df.copy()
        self.collaborative = collaborative_recommender

        self.neighbors = UserBasedEmbeddingsRecommender(
            collaborative_recommender=self.collaborative,
            ratings_df=self.ratings_df,
            movies_df=self.movies_df,
            min_votes=min_neighbor_votes,
        )

        self.memory_decay = float(memory_decay)
        self.max_history_signatures = int(max_history_signatures)
        self.min_catalog_votes = int(min_catalog_votes)
        self.min_neighbor_votes = int(min_neighbor_votes)

        # Memoria local en runtime para rotación si el cliente no manda estado.
        self._runtime_state = {"signatures": {}}

    def _normalize(self, series: pd.Series) -> pd.Series:
        """
        Normaliza una columna a rango 0-1.
        """
        min_value = float(series.min()) if len(series) else 0.0
        max_value = float(series.max()) if len(series) else 0.0

        if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
            return pd.Series([0.0] * len(series), index=series.index)

        return (series - min_value) / (max_value - min_value)

    def _empty_result(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.EMPTY_COLUMNS)

    @staticmethod
    def _safe_user_ratings_df(user_ratings_df: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Limpia y valida los ratings del usuario actual.
        """
        if user_ratings_df is None:
            return pd.DataFrame(columns=["movieId", "rating"])

        df = user_ratings_df.copy()

        if df.empty:
            return pd.DataFrame(columns=["movieId", "rating"])

        required = {"movieId", "rating"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"user_ratings_df debe tener columnas {sorted(required)}. "
                f"Faltan: {sorted(missing)}"
            )

        df = df.dropna(subset=["movieId", "rating"])
        if df.empty:
            return pd.DataFrame(columns=["movieId", "rating"])

        df["movieId"] = df["movieId"].astype(int)
        df["rating"] = df["rating"].astype(float).clip(0.5, 5.0)
        return df

    @staticmethod
    def _clean_preferences(
        user_preferences: Optional[Mapping[str, float]],
    ) -> dict[str, float]:
        return normalize_user_preferences(user_preferences)

    def _build_shortlist(
        self,
        candidate_ids: list[int],
        user_preferences: Optional[Mapping[str, float]],
        shortlist_size: int = 300,
    ) -> pd.DataFrame:
        """
        Genera shortlist inicial por contenido.
        """
        baseline_pool = compute_baseline_scores(
            movie_ids=candidate_ids,
            movies_df=self.movies_df,
            user_preferences=user_preferences,
            min_votes=self.min_catalog_votes,
        )

        if baseline_pool.empty:
            return baseline_pool

        shortlist_size = max(shortlist_size, 50)
        return (
            baseline_pool.sort_values("baseline_score", ascending=False)
            .head(shortlist_size)
            .reset_index(drop=True)
        )

    def _get_weights(
        self,
        num_user_ratings: int,
        has_preferences: bool,
    ) -> dict[str, float]:
        """
        Política simple de pesos.

        Cuanto menos historial tenga el usuario:
        - más pesa contenido

        Cuanto más historial real tenga:
        - más pueden pesar colaborativo y vecinos
        """
        if num_user_ratings <= 0:
            return {"svd": 0.00, "embedding": 0.00, "content": 1.00}

        if num_user_ratings < 5:
            if has_preferences:
                return {"svd": 0.25, "embedding": 0.20, "content": 0.55}
            return {"svd": 0.40, "embedding": 0.25, "content": 0.35}

        if num_user_ratings < 15:
            if has_preferences:
                return {"svd": 0.35, "embedding": 0.25, "content": 0.40}
            return {"svd": 0.48, "embedding": 0.27, "content": 0.25}

        if has_preferences:
            return {"svd": 0.45, "embedding": 0.30, "content": 0.25}
        return {"svd": 0.55, "embedding": 0.30, "content": 0.15}

    def _make_request_signature(
        self,
        user_id: int | str | None,
        user_preferences: Mapping[str, float],
        user_ratings_df: pd.DataFrame,
        top_n: int,
        shortlist_size: int,
    ) -> str:
        """
        Genera una firma estable para detectar peticiones equivalentes.

        El `user_id` se usa aquí solo como parte de la identidad de la petición,
        no como usuario conocido del modelo.
        """
        ratings_payload = (
            user_ratings_df[["movieId", "rating"]]
            .sort_values(["movieId", "rating"])
            .to_dict(orient="records")
        )

        payload = {
            "user_id": user_id,
            "preferences": dict(sorted(user_preferences.items())),
            "ratings": ratings_payload,
            "top_n": int(top_n),
            "shortlist_size": int(shortlist_size),
        }

        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _deterministic_jitter(signature: str, movie_id: int, round_number: int) -> float:
        """
        Jitter pequeño, determinista y reproducible.

        Sirve para:
        - romper empates
        - evitar órdenes exactamente idénticos
        """
        token = f"{signature}|{movie_id}|{round_number}".encode("utf-8")
        digest = hashlib.sha256(token).hexdigest()
        value = int(digest[:8], 16) / 0xFFFFFFFF
        return (value - 0.5) * 0.03

    def _trim_state(self, state: dict) -> dict:
        """
        Limita el tamaño del estado histórico para que no crezca sin control.
        """
        signatures = state.setdefault("signatures", {})
        if len(signatures) <= self.max_history_signatures:
            return state

        ordered = sorted(
            signatures.items(),
            key=lambda item: item[1].get("request_count", 0),
            reverse=True,
        )[: self.max_history_signatures]

        state["signatures"] = dict(ordered)
        return state

    def _apply_rotation(
        self,
        df: pd.DataFrame,
        *,
        top_n: int,
        signature: str,
        state: Optional[dict] = None,
    ) -> tuple[pd.DataFrame, dict, dict]:
        """
        Penaliza suavemente películas recién servidas.

        Objetivo:
        - no repetir siempre exactamente lo mismo
        - no banear para siempre recomendaciones fuertes
        - introducir variedad de forma gradual y reversible
        """
        if df.empty:
            working_state = deepcopy(state) if state is not None else deepcopy(self._runtime_state)
            return df, working_state, {"request_count": 0, "signature": signature}

        working_state = deepcopy(state) if state is not None else deepcopy(self._runtime_state)
        signatures = working_state.setdefault("signatures", {})
        memory = signatures.setdefault(signature, {"request_count": 0, "exposures": {}})

        # Decaimiento: con el tiempo, lo ya mostrado pesa menos.
        exposures = {
            int(movie_id): float(value) * self.memory_decay
            for movie_id, value in memory.get("exposures", {}).items()
            if float(value) * self.memory_decay > 0.05
        }

        round_number = int(memory.get("request_count", 0)) + 1

        rotated = df.copy()
        penalties = []
        jitters = []

        for movie_id in rotated["movieId"].astype(int):
            exposure = exposures.get(int(movie_id), 0.0)
            penalty = min(exposure * 0.085, 0.22)
            jitter = self._deterministic_jitter(signature, int(movie_id), round_number)
            penalties.append(penalty)
            jitters.append(jitter)

        rotated["rotation_penalty"] = penalties
        rotated["rotation_jitter"] = jitters
        rotated["rotated_score"] = (
            rotated["final_score"] - rotated["rotation_penalty"] + rotated["rotation_jitter"]
        )

        rotated = rotated.sort_values(
            ["rotated_score", "final_score", "num_ratings"],
            ascending=[False, False, False],
        ).head(top_n).reset_index(drop=True)

        for movie_id in rotated["movieId"].astype(int):
            exposures[int(movie_id)] = exposures.get(int(movie_id), 0.0) + 1.0

        memory["request_count"] = round_number
        memory["exposures"] = exposures
        working_state = self._trim_state(working_state)

        if state is None:
            self._runtime_state = deepcopy(working_state)

        rotation_meta = {
            "signature": signature,
            "request_count": round_number,
            "tracked_movies": len(exposures),
        }
        return rotated, working_state, rotation_meta

    def _cold_start(
        self,
        user_preferences: Optional[Mapping[str, float]],
        top_n: int = 10,
    ) -> tuple[pd.DataFrame, dict]:
        """
        Camino de cold start:
        - sin ratings del usuario
        - solo contenido / catálogo
        """
        candidate_ids = self.movies_df["movieId"].astype(int).tolist()

        baseline = compute_baseline_scores(
            movie_ids=candidate_ids,
            movies_df=self.movies_df,
            user_preferences=user_preferences,
            min_votes=self.min_catalog_votes,
        )

        if baseline.empty:
            return self._empty_result(), {
                "path": "cold_start_empty",
                "weights": {"svd": 0.0, "embedding": 0.0, "content": 1.0},
            }

        baseline["svd_score"] = 0.0
        baseline["embedding_score"] = 0.0
        baseline["final_score"] = baseline["baseline_score"]
        baseline["rotated_score"] = baseline["final_score"]
        baseline["rotation_penalty"] = 0.0
        baseline["rotation_jitter"] = 0.0

        baseline = baseline.sort_values("final_score", ascending=False).head(top_n)
        return baseline.reset_index(drop=True), {
            "path": "cold_start_content_only",
            "weights": {"svd": 0.0, "embedding": 0.0, "content": 1.0},
        }

    @staticmethod
    def _matched_genres(
        genres: object,
        preferences: Mapping[str, float],
    ) -> list[str]:
        """
        Devuelve géneros de la película que también aparecen en preferencias.
        """
        movie_genres = normalize_genres(genres)
        return [genre for genre in movie_genres if genre in preferences]

    def _to_records(
        self,
        df: pd.DataFrame,
        *,
        preferences: Optional[Mapping[str, float]] = None,
    ) -> list[dict]:
        """
        Convierte el DataFrame interno a lista de diccionarios serializable.
        """
        if df.empty:
            return []

        preferences = preferences or {}
        payload = df.copy()

        for column in [
            "rating",
            "num_ratings",
            "baseline_score",
            "svd_score",
            "embedding_score",
            "final_score",
            "rotated_score",
            "rotation_penalty",
            "rotation_jitter",
            "genre_score",
            "rating_score",
            "popularity_score",
        ]:
            if column in payload.columns:
                payload[column] = payload[column].astype(float)

        records = payload.to_dict(orient="records")
        for record in records:
            record["genres"] = normalize_genres(record.get("genres", []))
            record["matched_genres"] = self._matched_genres(
                genres=record.get("genres", []),
                preferences=preferences,
            )

        return records

    def recommend_with_metadata(
        self,
        user_id: int | str | None,
        user_preferences: Optional[Mapping[str, float]],
        user_ratings_df: Optional[pd.DataFrame],
        top_n: int = 10,
        shortlist_size: int = 300,
        recommendation_state: Optional[dict] = None,
        apply_rotation: bool = True,
    ) -> dict:
        """
        Ejecuta el flujo completo y devuelve:
        - DataFrame interno
        - recomendaciones serializadas
        - metadata
        - recommendation_state actualizado
        """
        if top_n <= 0:
            return {
                "recommendations_df": self._empty_result(),
                "recommendations": [],
                "metadata": {
                    "path": "empty_top_n",
                    "weights": {"svd": 0.0, "embedding": 0.0, "content": 0.0},
                    "external_user_only": True,
                },
                "recommendation_state": deepcopy(
                    recommendation_state if recommendation_state is not None else self._runtime_state
                ),
            }

        preferences = self._clean_preferences(user_preferences)
        safe_user_ratings = self._safe_user_ratings_df(user_ratings_df)
        seen_ids = set(safe_user_ratings["movieId"].tolist())
        num_user_ratings = int(len(safe_user_ratings))

        signature = self._make_request_signature(
            user_id=user_id,
            user_preferences=preferences,
            user_ratings_df=safe_user_ratings,
            top_n=top_n,
            shortlist_size=shortlist_size,
        )

        # ----------------------------------------------------
        # 1) COLD START: si el usuario no trae ratings
        # ----------------------------------------------------
        if num_user_ratings == 0:
            cold_df, cold_meta = self._cold_start(preferences, top_n=top_n)

            if apply_rotation:
                cold_df, updated_state, rotation_meta = self._apply_rotation(
                    cold_df,
                    top_n=top_n,
                    signature=signature,
                    state=recommendation_state,
                )
            else:
                updated_state = deepcopy(
                    recommendation_state if recommendation_state is not None else self._runtime_state
                )
                rotation_meta = {"signature": signature, "request_count": 1, "tracked_movies": 0}

            metadata = {
                **cold_meta,
                "num_user_ratings": num_user_ratings,
                "num_preferences": len(preferences),
                "external_user_only": True,
                "used_temp_profile": False,
                "svd_candidates_scored": 0,
                "embedding_candidates_scored": 0,
                "rotation": rotation_meta,
            }

            return {
                "recommendations_df": cold_df,
                "recommendations": self._to_records(cold_df, preferences=preferences),
                "metadata": metadata,
                "recommendation_state": updated_state,
            }

        # ----------------------------------------------------
        # 2) Universo candidato: quitamos pelis ya vistas
        # ----------------------------------------------------
        candidate_ids = [
            int(movie_id)
            for movie_id in self.movies_df["movieId"].astype(int).tolist()
            if int(movie_id) not in seen_ids
        ]
        if not candidate_ids:
            return {
                "recommendations_df": self._empty_result(),
                "recommendations": [],
                "metadata": {
                    "path": "no_candidates",
                    "weights": {"svd": 0.0, "embedding": 0.0, "content": 0.0},
                    "num_user_ratings": num_user_ratings,
                    "num_preferences": len(preferences),
                    "external_user_only": True,
                },
                "recommendation_state": deepcopy(
                    recommendation_state if recommendation_state is not None else self._runtime_state
                ),
            }

        # ----------------------------------------------------
        # 3) Shortlist por contenido
        # ----------------------------------------------------
        baseline_pool = self._build_shortlist(
            candidate_ids=candidate_ids,
            user_preferences=preferences,
            shortlist_size=shortlist_size,
        )

        if baseline_pool.empty:
            cold_df, cold_meta = self._cold_start(preferences, top_n=top_n)
            return {
                "recommendations_df": cold_df,
                "recommendations": self._to_records(cold_df, preferences=preferences),
                "metadata": {
                    **cold_meta,
                    "path": "fallback_cold_start_after_empty_shortlist",
                    "num_user_ratings": num_user_ratings,
                    "num_preferences": len(preferences),
                    "external_user_only": True,
                },
                "recommendation_state": deepcopy(
                    recommendation_state if recommendation_state is not None else self._runtime_state
                ),
            }

        shortlist_ids = baseline_pool["movieId"].astype(int).tolist()

        df = baseline_pool[
            [
                "movieId",
                "title",
                "genres",
                "rating",
                "num_ratings",
                "baseline_score",
                "genre_score",
                "rating_score",
                "popularity_score",
            ]
        ].copy()

        df["svd_score"] = 0.0
        df["embedding_score"] = 0.0

        # ----------------------------------------------------
        # 4) Señal colaborativa temporal
        # ----------------------------------------------------
        svd_df = self.collaborative.score_candidates(
            user_id=user_id,  # el módulo lo ignora a propósito
            candidate_ids=shortlist_ids,
            movies_df=self.movies_df,
            user_ratings_df=safe_user_ratings,
        )[["movieId", "svd_score"]]

        # ----------------------------------------------------
        # 5) Vecinos similares históricos
        # ----------------------------------------------------
        emb_df = self.neighbors.score_candidates(
            user_id=user_id,  # se ignora, se usa solo user_ratings_df
            seen_movie_ids=seen_ids,
            candidate_ids=shortlist_ids,
            user_ratings_df=safe_user_ratings,
        )[["movieId", "embedding_score"]]

        if not svd_df.empty:
            df = df.merge(svd_df, on="movieId", how="left", suffixes=("", "_new"))
            df["svd_score"] = df["svd_score_new"].fillna(df["svd_score"])
            df = df.drop(columns=["svd_score_new"])

        if not emb_df.empty:
            df = df.merge(emb_df, on="movieId", how="left", suffixes=("", "_new"))
            df["embedding_score"] = df["embedding_score_new"].fillna(df["embedding_score"])
            df = df.drop(columns=["embedding_score_new"])

        df["svd_score"] = df["svd_score"].fillna(0.0).astype(float)
        df["embedding_score"] = df["embedding_score"].fillna(0.0).astype(float)

        # Normalizamos solo las señales colaborativas, no el baseline.
        if df["svd_score"].nunique() > 1:
            df["svd_score"] = self._normalize(df["svd_score"])

        if df["embedding_score"].nunique() > 1:
            df["embedding_score"] = self._normalize(df["embedding_score"])

        # ----------------------------------------------------
        # 6) Mezcla final
        # ----------------------------------------------------
        weights = self._get_weights(
            num_user_ratings=num_user_ratings,
            has_preferences=bool(preferences),
        )

        df["final_score"] = (
            weights["svd"] * df["svd_score"]
            + weights["embedding"] * df["embedding_score"]
            + weights["content"] * df["baseline_score"]
        )

        df = df.sort_values("final_score", ascending=False).reset_index(drop=True)

        # ----------------------------------------------------
        # 7) Rotación / diversidad
        # ----------------------------------------------------
        if apply_rotation:
            df, updated_state, rotation_meta = self._apply_rotation(
                df,
                top_n=top_n,
                signature=signature,
                state=recommendation_state,
            )
        else:
            df = df.head(top_n).reset_index(drop=True)
            df["rotation_penalty"] = 0.0
            df["rotation_jitter"] = 0.0
            df["rotated_score"] = df["final_score"]
            updated_state = deepcopy(
                recommendation_state if recommendation_state is not None else self._runtime_state
            )
            rotation_meta = {"signature": signature, "request_count": 1, "tracked_movies": 0}

        metadata = {
            "path": "hybrid_content_plus_temp_profile_plus_neighbors",
            "weights": weights,
            "num_user_ratings": num_user_ratings,
            "num_preferences": len(preferences),
            "candidate_pool_size": len(candidate_ids),
            "shortlist_size": len(shortlist_ids),
            "external_user_only": True,
            "used_temp_profile": True,
            "svd_candidates_scored": int(len(svd_df)),
            "embedding_candidates_scored": int(len(emb_df)),
            "rotation": rotation_meta,
        }

        return {
            "recommendations_df": df.reset_index(drop=True),
            "recommendations": self._to_records(df.reset_index(drop=True), preferences=preferences),
            "metadata": metadata,
            "recommendation_state": updated_state,
        }

    def recommend_payload(
        self,
        user_id: int | str | None,
        user_preferences: Optional[Mapping[str, float]],
        user_ratings_df: Optional[pd.DataFrame],
        top_n: int = 10,
        shortlist_size: int = 300,
        recommendation_state: Optional[dict] = None,
        apply_rotation: bool = True,
        include_metadata: bool = True,
    ) -> dict | list[dict]:
        """
        Versión lista para serializar en servicio o API.
        """
        result = self.recommend_with_metadata(
            user_id=user_id,
            user_preferences=user_preferences,
            user_ratings_df=user_ratings_df,
            top_n=top_n,
            shortlist_size=shortlist_size,
            recommendation_state=recommendation_state,
            apply_rotation=apply_rotation,
        )

        if not include_metadata:
            return result["recommendations"]

        return {
            "recommendations": result["recommendations"],
            "metadata": result["metadata"],
            "recommendation_state": result["recommendation_state"],
        }
