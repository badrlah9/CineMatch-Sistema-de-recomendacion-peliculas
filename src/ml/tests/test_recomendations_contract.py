"""
Test: Recommendations API Contract

Qué comprueba:
- Que el endpoint POST /v1/recommendations funciona correctamente
- Que la estructura del JSON de respuesta es la esperada
- Que los campos principales (recommendations, metadata, scores, etc.) existen

Cómo funciona:
- Sustituye el servicio ML real por un FakeService
- Evita cargar el modelo TensorFlow y los datos reales

Objetivo:
Garantizar que el contrato de la API se mantiene estable para el backend/frontend.
"""





from fastapi.testclient import TestClient

import fastapi_app
from cinematch.schemas import (
    MovieRecommendation,
    RecommendationMetadata,
    RecommendationResponse,
    RecommendationScores,
)


class FakeCineMatchService:
    def recommend(self, request):
        return RecommendationResponse(
            ok=True,
            service="CineMatch",
            model_version="test-version",
            recommendations=[
                MovieRecommendation(
                    movieId=1,
                    title="Toy Story (1995)",
                    genres=["Adventure", "Animation", "Children"],
                    matched_genres=["Adventure"],
                    catalog_rating=4.1,
                    num_ratings=1000,
                    scores=RecommendationScores(
                        final=0.95,
                        content=0.8,
                        collaborative=0.7,
                        neighbors=0.6,
                    ),
                    reason="Encaja con tus gustos en Adventure.",
                )
            ],
            metadata=RecommendationMetadata(
                path="test",
                num_user_ratings=1,
                num_preferences=2,
                shortlist_size=300,
            ),
            recommendation_state={},
        )


def test_recommendations_endpoint_contract():
    fastapi_app.service = FakeCineMatchService()

    client = TestClient(fastapi_app.app)

    payload = {
        "user_id": "test_user",
        "user_preferences": {
            "Adventure": 5,
            "Comedy": 3,
        },
        "ratings": [
            {
                "movieId": 1,
                "rating": 4.5,
            }
        ],
        "top_n": 10,
        "shortlist_size": 300,
        "apply_rotation": True,
        "include_debug_scores": True,
    }

    response = client.post("/v1/recommendations", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["ok"] is True
    assert data["service"] == "CineMatch"
    assert "recommendations" in data
    assert len(data["recommendations"]) == 1

    movie = data["recommendations"][0]

    assert movie["movieId"] == 1
    assert movie["title"] == "Toy Story (1995)"
    assert "scores" in movie
    assert "final" in movie["scores"]
    assert "metadata" in data