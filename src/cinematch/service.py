from __future__ import annotations

"""
Servicio de alto nivel de CineMatch.

Este es el punto más cómodo para FastAPI:
- carga datos y modelo una sola vez
- convierte request -> DataFrame
- llama al orquestador
- prepara una respuesta limpia para el backend
"""

import time

import pandas as pd

from cinematch.collaborative_tf import TensorFlowCollaborativeRecommender
from cinematch.config import ServiceSettings
from cinematch.content_based import enrich_movies_with_stats, normalize_genres
from cinematch.hybrid_orchestrator import HybridOrchestrator
from cinematch.io_utils import load_table
from cinematch.schemas import (
    MovieRecommendation,
    RecommendationMetadata,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationScores,
)


class CineMatchService:
    def __init__(self, settings: ServiceSettings) -> None:
        self.settings = settings

        movies_df = load_table(settings.movies_path)
        ratings_df = load_table(settings.ratings_path)

        # Si el catálogo no trae rating medio ni número de votos,
        # lo enriquecemos a partir de ratings históricos.
        required_stats = {"rating", "num_ratings"}
        if not required_stats.issubset(movies_df.columns):
            movies_df = enrich_movies_with_stats(movies_df, ratings_df)

        self.movies_df = movies_df
        self.ratings_df = ratings_df

        self.collaborative = TensorFlowCollaborativeRecommender(
            model_path=str(settings.model_path),
            mappings_path=str(settings.mappings_path),
            metadata_path=str(settings.metadata_path),
        )

        self.orchestrator = HybridOrchestrator(
            collaborative_recommender=self.collaborative,
            ratings_df=self.ratings_df,
            movies_df=self.movies_df,
            memory_decay=settings.rotation_memory_decay,
            max_history_signatures=settings.max_history_signatures,
            min_catalog_votes=settings.min_catalog_votes,
            min_neighbor_votes=settings.min_neighbor_votes,
        )

    @property
    def ready(self) -> bool:
        return True

    def _build_reason(
        self,
        *,
        row: dict,
        matched_genres: list[str],
    ) -> str:
        """
        Genera una explicación breve, legible y utilizable por el backend.

        No pretende ser una explicación perfecta, pero sí útil:
        - gustos del usuario
        - fuerza de la señal colaborativa
        - soporte del catálogo
        """
        parts: list[str] = []

        if matched_genres:
            pretty_genres = ", ".join(matched_genres[:3])
            parts.append(f"encaja con tus gustos en {pretty_genres}")

        if float(row.get("svd_score", 0.0)) >= 0.70:
            parts.append("tu patrón de ratings la deja muy arriba")

        if float(row.get("embedding_score", 0.0)) >= 0.70:
            parts.append("usuarios con gustos parecidos la valoraron bien")

        if int(float(row.get("num_ratings", 0))) >= 100:
            parts.append("tiene una base sólida de valoraciones")

        if not parts:
            parts.append("combina buena calidad de catálogo y señal híbrida equilibrada")

        sentence = "; ".join(parts)
        return sentence[:1].upper() + sentence[1:] + "."

    def _to_api_response(
        self,
        raw_payload: dict,
        *,
        latency_ms: float,
        include_debug_scores: bool,
    ) -> RecommendationResponse:
        """
        Convierte el payload interno del orquestador a esquemas API.
        """
        raw_recommendations = raw_payload.get("recommendations", [])
        raw_metadata = dict(raw_payload.get("metadata", {}))
        raw_metadata["latency_ms"] = round(latency_ms, 2)

        recommendations: list[MovieRecommendation] = []
        for item in raw_recommendations:
            genres = normalize_genres(item.get("genres", []))
            matched_genres = normalize_genres(item.get("matched_genres", []))

            if include_debug_scores:
                scores = RecommendationScores(
                    final=round(float(item.get("rotated_score", item.get("final_score", 0.0))), 6),
                    content=round(float(item.get("baseline_score", 0.0)), 6),
                    collaborative=round(float(item.get("svd_score", 0.0)), 6),
                    neighbors=round(float(item.get("embedding_score", 0.0)), 6),
                )
            else:
                scores = RecommendationScores(
                    final=round(float(item.get("rotated_score", item.get("final_score", 0.0))), 6),
                    content=0.0,
                    collaborative=0.0,
                    neighbors=0.0,
                )

            recommendation = MovieRecommendation(
                movieId=int(item["movieId"]),
                title=str(item.get("title", "Sin título")),
                genres=genres,
                matched_genres=matched_genres,
                catalog_rating=round(float(item.get("rating", 0.0)), 4),
                num_ratings=int(float(item.get("num_ratings", 0))),
                scores=scores,
                reason=self._build_reason(row=item, matched_genres=matched_genres),
            )
            recommendations.append(recommendation)

        metadata = RecommendationMetadata(**raw_metadata)

        return RecommendationResponse(
            ok=True,
            service=self.settings.service_name,
            model_version=self.settings.model_version,
            recommendations=recommendations,
            metadata=metadata,
            recommendation_state=raw_payload.get("recommendation_state"),
        )

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        Ejecuta una recomendación de extremo a extremo:
        request -> DataFrame -> orquestador -> respuesta API
        """
        start = time.perf_counter()

        user_ratings_df = pd.DataFrame(
            [rating.model_dump() for rating in request.ratings],
            columns=["movieId", "rating"],
        )

        raw_payload = self.orchestrator.recommend_payload(
            user_id=request.user_id,
            user_preferences=request.user_preferences,
            user_ratings_df=user_ratings_df,
            top_n=request.top_n or self.settings.default_top_n,
            shortlist_size=request.shortlist_size or self.settings.default_shortlist_size,
            recommendation_state=request.recommendation_state,
            apply_rotation=request.apply_rotation,
            include_metadata=True,
        )

        latency_ms = (time.perf_counter() - start) * 1000.0
        return self._to_api_response(
            raw_payload=raw_payload,
            latency_ms=latency_ms,
            include_debug_scores=request.include_debug_scores,
        )
