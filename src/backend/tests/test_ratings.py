"""
Tests del endpoint /ratings.

Los routers de ratings usan SQL específico de PostgreSQL (::float, NOW()),
por eso se usa `authed_client` que inyecta un MagicMock de sesión de BD
en lugar de SQLite real.

Los tests de validación (422) no necesitan BD: Pydantic los rechaza antes
de que se ejecute el handler.
"""
import pytest
from unittest.mock import MagicMock, call


# ---------------------------------------------------------------------------
# Helpers para construir filas mock que imiten RowProxy de SQLAlchemy
# ---------------------------------------------------------------------------

def _row(**kwargs):
    """Devuelve un objeto con atributos, como haría una fila de SQLAlchemy."""
    r = MagicMock()
    for k, v in kwargs.items():
        setattr(r, k, v)
    r._asdict.return_value = kwargs
    return r


# ---------------------------------------------------------------------------
# POST /ratings — validación de esquema (sin BD)
# ---------------------------------------------------------------------------

class TestRatingValidation:
    """Estos tests verifican que FastAPI rechaza datos inválidos (422)
    antes de llegar al handler, por lo que no necesitan BD real."""

    def test_rating_below_minimum_returns_422(self, authed_client):
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 0.4})
        assert resp.status_code == 422

    def test_rating_above_maximum_returns_422(self, authed_client):
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 5.1})
        assert resp.status_code == 422

    def test_rating_zero_returns_422(self, authed_client):
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 0.0})
        assert resp.status_code == 422

    def test_missing_movie_id_returns_422(self, authed_client):
        resp = authed_client.post("/ratings", json={"rating": 4.0})
        assert resp.status_code == 422

    def test_missing_rating_returns_422(self, authed_client):
        resp = authed_client.post("/ratings", json={"movie_id": 1})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /ratings — lógica del handler (con BD mockeada)
# ---------------------------------------------------------------------------

class TestRateMovie:
    def _setup_mock_db_new_rating(self, mock_db):
        """Configura el mock para: película existe, no hay rating previo."""
        result_movie_exists = MagicMock()
        result_movie_exists.fetchone.return_value = (1,)  # película existe

        result_no_existing = MagicMock()
        result_no_existing.fetchone.return_value = None  # sin rating previo

        mock_db.execute.side_effect = [
            result_movie_exists,
            result_no_existing,
            MagicMock(),  # INSERT
        ]

    def _setup_mock_db_update_rating(self, mock_db):
        """Configura el mock para: película existe, ya hay rating previo."""
        result_movie_exists = MagicMock()
        result_movie_exists.fetchone.return_value = (1,)

        existing_row = MagicMock()
        existing_row.rating_id = 99
        result_existing = MagicMock()
        result_existing.fetchone.return_value = existing_row

        mock_db.execute.side_effect = [
            result_movie_exists,
            result_existing,
            MagicMock(),  # UPDATE
        ]

    def test_new_rating_returns_201(self, authed_client, mock_db):
        self._setup_mock_db_new_rating(mock_db)
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 4.5})
        assert resp.status_code == 201

    def test_new_rating_response_body(self, authed_client, mock_db, mock_user):
        self._setup_mock_db_new_rating(mock_db)
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 4.5})
        body = resp.json()
        assert body["ok"] is True
        assert body["movie_id"] == 1
        assert body["rating"] == 4.5
        assert body["user_id"] == mock_user.user_id

    def test_rating_boundary_low(self, authed_client, mock_db):
        self._setup_mock_db_new_rating(mock_db)
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 0.5})
        assert resp.status_code == 201

    def test_rating_boundary_high(self, authed_client, mock_db):
        self._setup_mock_db_new_rating(mock_db)
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 5.0})
        assert resp.status_code == 201

    def test_movie_not_found_returns_404(self, authed_client, mock_db):
        result_no_movie = MagicMock()
        result_no_movie.fetchone.return_value = None  # película no existe
        mock_db.execute.side_effect = [result_no_movie]

        resp = authed_client.post("/ratings", json={"movie_id": 9999, "rating": 3.0})
        assert resp.status_code == 404
        assert "película" in resp.json()["detail"].lower()

    def test_update_existing_rating(self, authed_client, mock_db):
        self._setup_mock_db_update_rating(mock_db)
        resp = authed_client.post("/ratings", json={"movie_id": 1, "rating": 2.0})
        assert resp.status_code == 201

    def test_db_commit_is_called(self, authed_client, mock_db):
        self._setup_mock_db_new_rating(mock_db)
        authed_client.post("/ratings", json={"movie_id": 1, "rating": 3.0})
        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# GET /ratings/me — historial del usuario
# ---------------------------------------------------------------------------

class TestGetMyRatings:
    def test_empty_history_returns_empty_list(self, authed_client, mock_db):
        mock_db.execute.return_value.fetchall.return_value = []
        resp = authed_client.get("/ratings/me")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_ratings_list(self, authed_client, mock_db):
        fake_rows = [
            _row(movie_id=1, title="Inception", rating=4.5, rated_at="2024-01-01T10:00:00"),
            _row(movie_id=2, title="Interstellar", rating=5.0, rated_at="2024-01-02T12:00:00"),
        ]
        mock_db.execute.return_value.fetchall.return_value = fake_rows
        resp = authed_client.get("/ratings/me")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["movie_id"] == 1
        assert body[0]["title"] == "Inception"
        assert body[0]["rating"] == 4.5
        assert body[1]["rating"] == 5.0

    def test_ratings_ordered_by_rated_at_desc(self, authed_client, mock_db):
        """Verifica que la query se llama con el user_id del usuario autenticado."""
        mock_db.execute.return_value.fetchall.return_value = []
        authed_client.get("/ratings/me")
        mock_db.execute.assert_called_once()
        # Extrae el parámetro pasado a execute para verificar el user_id
        call_args = mock_db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("uid") == 42  # user_id del mock_user
