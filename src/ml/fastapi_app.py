from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Carga el .env del directorio donde vive este archivo (src/ml/.env)
load_dotenv(Path(__file__).resolve().parent / ".env")

"""
Aplicación FastAPI para exponer el servicio de recomendaciones.

Este fichero se mantiene intencionadamente pequeño:
- crea la app
- gestiona el ciclo de vida del servicio
- expone endpoints simples y fáciles de monitorizar

Endpoints:
- GET /health
- GET /ready
- POST /v1/recommendations
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from cinematch.config import build_settings
from cinematch.schemas import HealthResponse, RecommendationRequest, RecommendationResponse
from cinematch.service import CineMatchService


service: CineMatchService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Carga el servicio una sola vez al arrancar la aplicación.

    Así evitamos:
    - recargar modelo y artefactos en cada request
    - aumentar la latencia innecesariamente
    """
    global service
    settings = build_settings()
    service = CineMatchService(settings)
    yield
    service = None


app = FastAPI(
    title="CineMatch ML Service",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Endpoint de salud básico.
    """
    global service
    settings = build_settings()

    return HealthResponse(
        ok=True,
        service=settings.service_name,
        model_version=settings.model_version,
        ready=service is not None,
    )


@app.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    """
    Endpoint de readiness.
    """
    return health()


@app.post("/v1/recommendations", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest) -> RecommendationResponse:
    """
    Endpoint principal de inferencia.

    Si el servicio aún no estaba inicializado, se crea en caliente.
    """
    global service
    if service is None:
        settings = build_settings()
        service = CineMatchService(settings)

    return service.recommend(request)
