
"""
Orquestador central del sistema híbrido.

Este módulo es el corazón del refactor:
- combina contenido + colaborativo SVD + vecinos similares
- deja de depender de que el usuario exista en MovieLens
- añade rotación/diversidad para evitar respuestas idénticas
- devuelve metadatos útiles para depuración y para la API
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from collaborative_svd import Recommender
from content_based import compute_baseline_scores, normalize_user_preferences
from user_based_embeddings import UserBasedEmbeddingsRecommender


class HybridRecommender:
    """
    Flujo general del sistema:
    1) contenido genera una shortlist sensible a gustos y calidad
    2) SVD temporal puntúa la shortlist usando ratings del usuario
    3) vecinos similares en embeddings aportan otra señal colaborativa
    4) se mezclan scores con pesos adaptativos
    5) se aplica rotación suave para no repetir exactamente lo mismo
    """

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
    ]

    def __init__(
        self,
        model_path: str,
        ratings_df: pd.DataFrame,
        movies_df: pd.DataFrame,
        *,
        memory_decay: float = 0.80,
        max_history_signatures: int = 200,
    ) -> None:
        missing = self.REQUIRED_MOVIE_COLUMNS - set(movies_df.columns)
        if missing:
            raise ValueError(f"movies_df no tiene columnas necesarias: {sorted(missing)}")

        self.ratings_df = ratings_df.copy()
        self.movies_df = movies_df.copy()

        self.rec = Recommender(model_path)
        self.emb_cf = UserBasedEmbeddingsRecommender(
            self.rec,
            self.ratings_df,
            self.movies_df,
        )

        self.memory_decay = float(memory_decay)
        self.max_history_signatures = int(max_history_signatures)

        # Memoria en runtime para rotación si el cliente no trae su propio estado.
        self._runtime_state = {"signatures": {}}

    # --------------------------------------------------------
    # Utilidades generales
    # --------------------------------------------------------

    def _normalize(self, col: pd.Series) -> pd.Series:
        min_value = float(col.min()) if len(col) else 0.0
        max_value = float(col.max()) if len(col) else 0.0

        if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
            return pd.Series([0.0] * len(col), index=col.index)

        return (col - min_value) / (max_value - min_value)

    def _empty_result(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.EMPTY_COLUMNS)

    @staticmethod
    def _safe_user_ratings_df(user_ratings_df: Optional[pd.DataFrame]) -> pd.DataFrame:
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
        baseline_pool = compute_baseline_scores(
            movie_ids=candidate_ids,
            movies_df=self.movies_df,
            user_preferences=user_preferences,
            min_votes=10,
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
        Ajusta pesos según señal disponible del usuario.
        """
        if num_user_ratings <= 0:
            if has_preferences:
                return {"svd": 0.00, "embedding": 0.00, "content": 1.00}
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

    # --------------------------------------------------------
    # Diversidad y rotación de resultados
    # --------------------------------------------------------

    def _make_request_signature(
        self,
        user_id: int | str | None,
        user_preferences: Mapping[str, float],
        user_ratings_df: pd.DataFrame,
        top_n: int,
        shortlist_size: int,
    ) -> str:
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
        """
        token = f"{signature}|{movie_id}|{round_number}".encode("utf-8")
        digest = hashlib.sha256(token).hexdigest()
        value = int(digest[:8], 16) / 0xFFFFFFFF
        return (value - 0.5) * 0.03  # aprox. [-0.015, 0.015]

    def _trim_state(self, state: dict) -> dict:
        signatures = state.setdefault("signatures", {})
        if len(signatures) <= self.max_history_signatures:
            return state

        # Conserva las firmas más recientes.
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
        Penaliza suavemente películas recién servidas para que el top rote.

        Importante:
        - no las descarta para siempre
        - la memoria decae con el tiempo
        - con llamadas repetidas a la misma petición se van mezclando otras
        """
        if df.empty:
            state = deepcopy(state) if state is not None else deepcopy(self._runtime_state)
            return df, state, {"request_count": 0, "signature": signature}

        working_state = deepcopy(state) if state is not None else deepcopy(self._runtime_state)
        signatures = working_state.setdefault("signatures", {})
        memory = signatures.setdefault(signature, {"request_count": 0, "exposures": {}})

        # Decaimiento de memoria previa.
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

    # --------------------------------------------------------
    # Caminos del híbrido
    # --------------------------------------------------------

    def _cold_start(
        self,
        user_preferences: Optional[Mapping[str, float]],
        top_n: int = 10,
    ) -> tuple[pd.DataFrame, dict]:
        candidate_ids = self.movies_df["movieId"].astype(int).tolist()

        baseline = compute_baseline_scores(
            movie_ids=candidate_ids,
            movies_df=self.movies_df,
            user_preferences=user_preferences,
            min_votes=10,
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

    def recommend(
        self,
        user_id: int | str | None,
        user_preferences: Optional[Mapping[str, float]],
        user_ratings_df: Optional[pd.DataFrame],
        top_n: int = 10,
        shortlist_size: int = 300,
        recommendation_state: Optional[dict] = None,
        apply_rotation: bool = True,
    ) -> pd.DataFrame:
        """
        Devuelve solo el DataFrame final.
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
        return result["recommendations_df"]

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
        Devuelve recomendaciones + metadatos + estado de rotación.
        """
        if top_n <= 0:
            return {
                "recommendations_df": self._empty_result(),
                "recommendations": [],
                "metadata": {
                    "path": "empty_top_n",
                    "weights": {"svd": 0.0, "embedding": 0.0, "content": 0.0},
                },
                "recommendation_state": deepcopy(
                    recommendation_state if recommendation_state is not None else self._runtime_state
                ),
            }

        prefs = self._clean_preferences(user_preferences)
        safe_user_ratings = self._safe_user_ratings_df(user_ratings_df)
        seen_ids = set(safe_user_ratings["movieId"].tolist())
        num_user_ratings = int(len(safe_user_ratings))

        signature = self._make_request_signature(
            user_id=user_id,
            user_preferences=prefs,
            user_ratings_df=safe_user_ratings,
            top_n=top_n,
            shortlist_size=shortlist_size,
        )

        if num_user_ratings == 0:
            cold_df, cold_meta = self._cold_start(prefs, top_n=top_n)

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
                "num_preferences": len(prefs),
                "trained_user_available": self.rec.has_trained_user(user_id),
                "used_temp_profile": False,
                "rotation": rotation_meta,
            }

            return {
                "recommendations_df": cold_df,
                "recommendations": self._to_records(cold_df),
                "metadata": metadata,
                "recommendation_state": updated_state,
            }

        candidate_ids = [
            int(movie_id)
            for movie_id in self.movies_df["movieId"].astype(int).tolist()
            if int(movie_id) not in seen_ids
        ]
        if not candidate_ids:
            empty_df = self._empty_result()
            return {
                "recommendations_df": empty_df,
                "recommendations": [],
                "metadata": {
                    "path": "no_candidates",
                    "weights": {"svd": 0.0, "embedding": 0.0, "content": 0.0},
                    "num_user_ratings": num_user_ratings,
                    "num_preferences": len(prefs),
                },
                "recommendation_state": deepcopy(
                    recommendation_state if recommendation_state is not None else self._runtime_state
                ),
            }

        baseline_pool = self._build_shortlist(
            candidate_ids=candidate_ids,
            user_preferences=prefs,
            shortlist_size=shortlist_size,
        )
        if baseline_pool.empty:
            cold_df, cold_meta = self._cold_start(prefs, top_n=top_n)
            return {
                "recommendations_df": cold_df,
                "recommendations": self._to_records(cold_df),
                "metadata": {
                    **cold_meta,
                    "path": "fallback_cold_start_after_empty_shortlist",
                    "num_user_ratings": num_user_ratings,
                    "num_preferences": len(prefs),
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
            ]
        ].copy()

        df["svd_score"] = 0.0
        df["embedding_score"] = 0.0

        svd_df = self.rec.score_candidates(
            user_id=user_id,
            candidate_ids=shortlist_ids,
            movies_df=self.movies_df,
            user_ratings_df=safe_user_ratings,
        )[["movieId", "svd_score"]]

        emb_df = self.emb_cf.score_candidates(
            user_id=user_id,
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

        if df["svd_score"].nunique() > 1:
            df["svd_score"] = self._normalize(df["svd_score"])

        if df["embedding_score"].nunique() > 1:
            df["embedding_score"] = self._normalize(df["embedding_score"])

        weights = self._get_weights(
            num_user_ratings=num_user_ratings,
            has_preferences=bool(prefs),
        )

        df["final_score"] = (
            weights["svd"] * df["svd_score"]
            + weights["embedding"] * df["embedding_score"]
            + weights["content"] * df["baseline_score"]
        )

        df = df.sort_values("final_score", ascending=False).reset_index(drop=True)

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
            "path": "hybrid_content_plus_temp_svd_plus_neighbors",
            "weights": weights,
            "num_user_ratings": num_user_ratings,
            "num_preferences": len(prefs),
            "candidate_pool_size": len(candidate_ids),
            "shortlist_size": len(shortlist_ids),
            "trained_user_available": self.rec.has_trained_user(user_id),
            "used_temp_profile": True,
            "svd_candidates_scored": int(len(svd_df)),
            "embedding_candidates_scored": int(len(emb_df)),
            "rotation": rotation_meta,
        }

        return {
            "recommendations_df": df.reset_index(drop=True),
            "recommendations": self._to_records(df.reset_index(drop=True)),
            "metadata": metadata,
            "recommendation_state": updated_state,
        }

    # --------------------------------------------------------
    # Serialización
    # --------------------------------------------------------

    @staticmethod
    def _to_records(df: pd.DataFrame) -> list[dict]:
        if df.empty:
            return []

        payload = df.copy()

        for col in [
            "rating",
            "num_ratings",
            "baseline_score",
            "svd_score",
            "embedding_score",
            "final_score",
            "rotated_score",
            "rotation_penalty",
            "rotation_jitter",
        ]:
            if col in payload.columns:
                payload[col] = payload[col].astype(float)

        return payload.to_dict(orient="records")

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
        Devuelve un payload listo para FastAPI / JSON.

        Si `include_metadata=False`, devuelve solo la lista de recomendaciones.
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
