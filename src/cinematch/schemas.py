from __future__ import annotations

"""
Esquemas de entrada y salida para FastAPI.

Aquí viven las estructuras que el backend consumirá.
Eso hace que la API sea:
- clara
- estable
- fácil de documentar
"""

from typing import Any

from pydantic import BaseModel, Field


class UserRatingInput(BaseModel):
    movieId: int = Field(..., description="ID de la película valorada por el usuario.")
    rating: float = Field(..., ge=0.5, le=5.0, description="Rating del usuario entre 0.5 y 5.0.")


class RecommendationRequest(BaseModel):
    user_id: int | str | None = Field(
        default=None,
        description="ID del usuario externo a tu producto. No se usa como usuario conocido del train.",
    )
    user_preferences: dict[str, float] = Field(
        default_factory=dict,
        description="Preferencias por género, normalmente en escala 0-5.",
    )
    ratings: list[UserRatingInput] = Field(
        default_factory=list,
        description="Ratings recientes o históricos del usuario actual.",
    )
    top_n: int = Field(default=10, ge=1, le=100)
    shortlist_size: int = Field(default=300, ge=20, le=5000)
    recommendation_state: dict[str, Any] | None = Field(
        default=None,
        description="Estado opcional para rotación entre llamadas.",
    )
    apply_rotation: bool = Field(default=True)
    include_debug_scores: bool = Field(
        default=True,
        description="Si es False, la API devuelve una respuesta más ligera.",
    )


class RecommendationScores(BaseModel):
    final: float
    content: float
    collaborative: float
    neighbors: float


class MovieRecommendation(BaseModel):
    movieId: int
    title: str
    genres: list[str]
    matched_genres: list[str] = Field(default_factory=list)
    catalog_rating: float
    num_ratings: int
    scores: RecommendationScores
    reason: str


class RecommendationMetadata(BaseModel):
    path: str | None = None
    weights: dict[str, float] | None = None
    num_user_ratings: int | None = None
    num_preferences: int | None = None
    candidate_pool_size: int | None = None
    shortlist_size: int | None = None
    external_user_only: bool | None = None
    used_temp_profile: bool | None = None
    svd_candidates_scored: int | None = None
    embedding_candidates_scored: int | None = None
    rotation: dict[str, Any] | None = None
    latency_ms: float | None = None


class RecommendationResponse(BaseModel):
    ok: bool = True
    service: str
    model_version: str
    recommendations: list[MovieRecommendation]
    metadata: RecommendationMetadata
    recommendation_state: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    ok: bool = True
    service: str
    model_version: str
    ready: bool
