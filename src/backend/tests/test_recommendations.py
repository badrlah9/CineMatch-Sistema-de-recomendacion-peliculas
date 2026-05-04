"""
Tests del servicio de recomendaciones y del endpoint GET /recommendations/me.

Cubre:
- Las tres capas de fallback: ML → género → popularidad.
- La lógica de _get_user_preferences y _get_user_ratings (mocks de BD).
- Persistencia del recommendation_state entre llamadas.
- El endpoint /recommendations/me a través de authed_client.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.recommendations import (
    _get_user_preferences,
    _get_user_ratings,
    _load_recommendation_state,
    _save_recommendation_state,
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
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _recommend_by_popularity(db, k=5)
        params = db.execute.call_args[0][1]
        assert params["k"] == 5


# ---------------------------------------------------------------------------
# Tests de persistencia del recommendation_state
# ---------------------------------------------------------------------------

class TestRecommendationState:
    def test_load_returns_none_when_no_row(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        assert _load_recommendation_state(db, user_id=1) is None

    def test_load_returns_parsed_json(self):
        db = MagicMock()
        fake_row = MagicMock()
        fake_row.state = '{"signatures": {"abc": {"request_count": 1}}}'
        db.execute.return_value.fetchone.return_value = fake_row
        result = _load_recommendation_state(db, user_id=1)
        assert result == {"signatures": {"abc": {"request_count": 1}}}

    def test_save_calls_execute_and_commit(self):
        db = MagicMock()
        state = {"signatures": {"abc": {"request_count": 2, "exposures": {"10": 1.0}}}}
        _save_recommendation_state(db, user_id=1, state=state)
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_save_serializes_state_to_json(self):
        import json
        db = MagicMock()
        state = {"signatures": {"key": {"request_count": 3}}}
        _save_recommendation_state(db, user_id=1, state=state)
        params = db.execute.call_args[0][1]
        assert json.loads(params["state"]) == state


# ---------------------------------------------------------------------------
# Tests de integración del servicio get_recommendations (fallback completo)
# ---------------------------------------------------------------------------

class TestGetRecommendationsService:
    @pytest.mark.asyncio
    async def test_fallback_to_popularity_when_no_ml_no_genre(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []

        pop_rows = [
            _row(movie_id=i, title=f"Movie {i}", tmdb_id=i * 10,
                 total_ratings=100, avg_rating=4.0, score=3.9)
            for i in range(1, TOP_K + 1)
        ]

        with patch("app.services.recommendations._get_user_preferences", return_value={}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._load_recommendation_state", return_value=None), \
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
             patch("app.services.recommendations._load_recommendation_state", return_value=None), \
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
        new_state = {"signatures": {"sig123": {"request_count": 1, "exposures": {"10": 1.0}}}}
        ml_items = [{"movie_id": 10, "score": 0.95}]

        db_row = MagicMock()
        db_row.movie_id = 10
        db_row.title = "ML Movie"
        db_row.tmdb_id = 555
        db.execute.return_value.fetchall.return_value = [db_row]

        with patch("app.services.recommendations._get_user_preferences",
                   return_value={"Drama": 4.0}), \
             patch("app.services.recommendations._get_user_ratings",
                   return_value=[{"movieId": 5, "rating": 4.0}]), \
             patch("app.services.recommendations._load_recommendation_state", return_value=None), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=(ml_items, new_state)), \
             patch("app.services.recommendations._save_recommendation_state") as mock_save, \
             patch("app.services.recommendations._get_genres_for_movies",
                   return_value={10: ["Drama"]}):

            result = await get_recommendations(user_id=1, db=db)

        assert result.source == "model"
        assert result.recommendations[0].movie_id == 10
        assert result.recommendations[0].score == 0.95
        # El estado actualizado debe haberse persistido
        mock_save.assert_called_once_with(db, 1, new_state)

    @pytest.mark.asyncio
    async def test_ml_state_passed_from_previous_call(self):
        """Verifica que el estado cargado de BD se pasa correctamente al ML."""
        db = MagicMock()
        prev_state = {"signatures": {"old_sig": {"request_count": 2}}}
        captured_payload = {}

        async def mock_ml(user_id, k, prefs, ratings, recommendation_state=None):
            captured_payload["state"] = recommendation_state
            return None  # simular ML no disponible → fallback

        with patch("app.services.recommendations._get_user_preferences", return_value={}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._load_recommendation_state",
                   return_value=prev_state), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   side_effect=mock_ml), \
             patch("app.services.recommendations._recommend_by_genre", return_value=[]), \
             patch("app.services.recommendations._recommend_by_popularity", return_value=[]), \
             patch("app.services.recommendations._get_genres_for_movies", return_value={}):

            await get_recommendations(user_id=1, db=db)

        assert captured_payload["state"] == prev_state

    @pytest.mark.asyncio
    async def test_state_not_saved_when_ml_returns_none_state(self):
        """Si el ML devuelve new_state=None, no se guarda nada."""
        db = MagicMock()
        ml_items = [{"movie_id": 10, "score": 0.9}]

        db_row = MagicMock()
        db_row.movie_id = 10
        db_row.title = "Movie"
        db_row.tmdb_id = None
        db.execute.return_value.fetchall.return_value = [db_row]

        with patch("app.services.recommendations._get_user_preferences", return_value={}), \
             patch("app.services.recommendations._get_user_ratings", return_value=[]), \
             patch("app.services.recommendations._load_recommendation_state", return_value=None), \
             patch("app.services.recommendations._fetch_from_ml_service",
                   new_callable=AsyncMock, return_value=(ml_items, None)), \
             patch("app.services.recommendations._save_recommendation_state") as mock_save, \
             patch("app.services.recommendations._get_genres_for_movies", return_value={}):

            await get_recommendations(user_id=1, db=db)

        mock_save.assert_not_called()


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
             patch("app.services.recommendations._load_recommendation_state", return_value=None), \
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
             patch("app.services.recommendations._load_recommendation_state", return_value=None), \
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
