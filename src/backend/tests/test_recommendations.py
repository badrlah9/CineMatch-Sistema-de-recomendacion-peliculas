"""
Tests del servicio de recomendaciones y del endpoint GET /recommendations/me.

Cubre:
- Las tres capas de fallback: ML → género → popularidad.
- La lógica de _get_user_preferences y _get_user_ratings (mocks de BD).
- El endpoint /recommendations/me a través de authed_client.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.recommendations import (
    _get_user_preferences,
    _get_user_ratings,
    _recommend_by_popularity,
    get_recommendations,
    TOP_K,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**kwargs):
    r = MagicMock()
    for k, v in kwargs.items():
        setattr(r, k, v)
    r._asdict.return_value = kwargs
    return r


# ---------------------------------------------------------------------------
# Tests unitarios de funciones auxiliares
# ---------------------------------------------------------------------------

class TestGetUserPreferences:
    def test_returns_dict_genre_score(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [
            _row(name="Action", score=4.5),
            _row(name="Drama", score=3.0),
        ]
        result = _get_user_preferences(db, user_id=1)
        assert result == {"Action": 4.5, "Drama": 3.0}

    def test_empty_preferences(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        result = _get_user_preferences(db, user_id=1)
        assert result == {}


class TestGetUserRatings:
    def test_returns_list_of_dicts(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [
            _row(movieId=1, rating=4.5),
            _row(movieId=2, rating=3.0),
        ]
        result = _get_user_ratings(db, user_id=1)
        assert result == [
            {"movieId": 1, "rating": 4.5},
            {"movieId": 2, "rating": 3.0},
        ]

    def test_empty_ratings(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        result = _get_user_ratings(db, user_id=1)
        assert result == []


class TestRecommendByPopularity:
    def test_returns_list(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [
            _row(movie_id=1, title="Movie A", tmdb_id=100,
                 total_ratings=1000, avg_rating=4.2, score=4.1),
        ]
        result = _recommend_by_popularity(db, k=1)
        assert len(result) == 1
        assert result[0]["movie_id"] == 1

    def test_respects_k_limit(self):
        """Verifica que el parámetro k se pasa a la query."""
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _recommend_by_popularity(db, k=5)
        call_args = db.execute.call_args
        params = call_args[0][1]
        assert params["k"] == 5


# ---------------------------------------------------------------------------
# Tests de integración del servicio get_recommendations (fallback completo)
# ---------------------------------------------------------------------------

class TestGetRecommendationsService:
    @pytest.mark.asyncio
    async def test_fallback_to_popularity_when_no_ml_no_genre(self):
        db = MagicMock()

        # Sin preferencias, sin ratings
        db.execute.return_value.fetchall.return_value = []

        pop_rows = [
            _row(movie_id=i, title=f"Movie {i}", tmdb_id=i * 10,
                 total_ratings=100, avg_rating=4.0, score=3.9)
            for i in range(1, TOP_K + 1)
        ]

        with patch("app.services.recommendations._get_user_preferences", return_value={}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.services.recommendations._recommend_by_genre", return_value=[]), \
             patch("app.services.recommendations._recommend_by_popularity",
                   return_value=[r._asdict() for r in pop_rows]), \
             patch("app.services.recommendations._get_genres_for_movies", return_value={}):

            result = await get_recommendations(user_id=1, db=db)

        assert result.source == "popularity"
        assert result.total == TOP_K

    @pytest.mark.asyncio
    async def test_fallback_to_genre_when_no_ml(self):
        db = MagicMock()
        genre_rows = [
            {"movie_id": 1, "title": "Genre Movie", "tmdb_id": 100,
             "avg_rating": 4.0, "total_ratings": 200, "score": 3.8}
        ]

        with patch("app.services.recommendations._get_user_preferences",
                   return_value={"Action": 5.0}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.services.recommendations._recommend_by_genre",
                   return_value=genre_rows), \
             patch("app.services.recommendations._get_genres_for_movies",
                   return_value={1: ["Action"]}):

            result = await get_recommendations(user_id=1, db=db)

        assert result.source == "genre_based"
        assert result.total == 1
        assert result.recommendations[0].genres == ["Action"]

    @pytest.mark.asyncio
    async def test_ml_result_takes_priority(self):
        db = MagicMock()
        ml_rows = [{"movie_id": 10, "score": 0.95}]
        db_row = MagicMock()
        db_row.movie_id = 10
        db_row.title = "ML Movie"
        db_row.tmdb_id = 555
        db.execute.return_value.fetchall.return_value = [db_row]

        with patch("app.services.recommendations._get_user_preferences",
                   return_value={"Drama": 4.0}), \
             patch("app.services.recommendations._get_user_ratings",
                   return_value=[{"movieId": 5, "rating": 4.0}]), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=ml_rows), \
             patch("app.services.recommendations._get_genres_for_movies",
                   return_value={10: ["Drama"]}):

            result = await get_recommendations(user_id=1, db=db)

        assert result.source == "model"
        assert result.recommendations[0].movie_id == 10
        assert result.recommendations[0].score == 0.95


# ---------------------------------------------------------------------------
# Tests del endpoint HTTP GET /recommendations/me
# ---------------------------------------------------------------------------

class TestRecommendationsEndpoint:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/recommendations/me")
        assert resp.status_code == 401

    def test_authenticated_returns_200(self, authed_client):
        pop_rows = [
            {"movie_id": i, "title": f"Movie {i}", "tmdb_id": None,
             "avg_rating": 4.0, "total_ratings": 100, "score": 3.8}
            for i in range(1, TOP_K + 1)
        ]
        with patch("app.services.recommendations._get_user_preferences", return_value={}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.services.recommendations._recommend_by_genre", return_value=[]), \
             patch("app.services.recommendations._recommend_by_popularity",
                   return_value=pop_rows), \
             patch("app.services.recommendations._get_genres_for_movies", return_value={}):

            resp = authed_client.get("/recommendations/me")

        assert resp.status_code == 200
        body = resp.json()
        assert "recommendations" in body
        assert body["source"] == "popularity"
        assert body["total"] == TOP_K

    def test_response_schema_fields(self, authed_client):
        pop_rows = [
            {"movie_id": 1, "title": "Test Movie", "tmdb_id": 100,
             "avg_rating": 4.0, "total_ratings": 50, "score": 3.9}
        ]
        with patch("app.services.recommendations._get_user_preferences", return_value={}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.services.recommendations._recommend_by_genre", return_value=[]), \
             patch("app.services.recommendations._recommend_by_popularity",
                   return_value=pop_rows), \
             patch("app.services.recommendations._get_genres_for_movies",
                   return_value={1: ["Action"]}):

            resp = authed_client.get("/recommendations/me")

        item = resp.json()["recommendations"][0]
        assert "movie_id" in item
        assert "title" in item
        assert "score" in item
        assert "genres" in item
        assert "source" in item
