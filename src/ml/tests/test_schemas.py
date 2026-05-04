"""
Test: Schemas (Validación de datos)

Qué comprueba:
- Que el modelo RecommendationRequest acepta datos válidos
- Que los campos (user_id, user_preferences, ratings, etc.) se parsean correctamente

Objetivo:
Garantizar que el formato de entrada del servicio ML es correcto
y no se rompe al cambiar los modelos de datos.
"""




from cinematch.schemas import RecommendationRequest


def test_recommendation_request_valid():
    request = RecommendationRequest(
        user_id="test_user",
        user_preferences={
            "Action": 5,
            "Comedy": 3,
        },
        ratings=[
            {
                "movieId": 1,
                "rating": 4.5,
            }
        ],
        top_n=10,
        shortlist_size=300,
    )

    assert request.user_id == "test_user"
    assert request.user_preferences["Action"] == 5
    assert request.ratings[0].movieId == 1
    assert request.ratings[0].rating == 4.5