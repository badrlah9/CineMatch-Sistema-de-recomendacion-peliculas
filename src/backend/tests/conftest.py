"""
Fixtures compartidos para toda la suite de tests del backend.

Estrategia de base de datos:
- SQLite basado en archivo (test_cinematch.db) reutilizando el engine de la
  app, configurado vía DATABASE_URL antes de importar ningún módulo.
  QueuePool (usado por SQLite de archivo) sí soporta pool_size/max_overflow.
- MagicMock de sesión para endpoints con SQL específico de PostgreSQL
  (::float, ANY(:ids), NOW()), que no son compatibles con SQLite.
"""
import os
import uuid

import pytest

# Env vars ANTES de cualquier import de la app para que get_settings() las capture.
os.environ["DATABASE_URL"] = "sqlite:///./test_cinematch.db"
os.environ["SECRET_KEY"] = "test-secret-key-cinematch-pytest"
os.environ.setdefault("TMDB_API_KEY", "")
os.environ.setdefault("ML_SERVICE_URL", "")

from sqlalchemy import text                        # noqa: E402
from sqlalchemy.orm import sessionmaker            # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from unittest.mock import MagicMock               # noqa: E402

from app.main import app                           # noqa: E402
from app.database import Base, get_db, engine     # noqa: E402
from app.dependencies import get_current_user      # noqa: E402
from app.config import get_settings                # noqa: E402
from app.models import User                        # noqa: E402

get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Inicialización única del esquema para toda la sesión de pytest
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cinematch_ratings (
                rating_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                movie_id   INTEGER NOT NULL,
                rating     REAL    NOT NULL CHECK (rating >= 0.5 AND rating <= 5.0),
                rated_at   TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                UNIQUE (user_id, movie_id)
            )
        """))
        conn.execute(text(
            "INSERT OR IGNORE INTO movies (movie_id, title) VALUES (1, 'Test Movie')"
        ))
        conn.commit()

    yield

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_cinematch.db"):
        os.remove("./test_cinematch.db")


# ---------------------------------------------------------------------------
# Sesión de BD por test
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# TestClient con sesión SQLite (para endpoints ORM: auth, preferences)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers de usuario
# ---------------------------------------------------------------------------

@pytest.fixture()
def unique_username():
    return f"user_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def registered_user(client, unique_username):
    resp = client.post("/auth/register", json={
        "username": unique_username,
        "password": "pass1234",
    })
    assert resp.status_code == 201, resp.text
    return {"username": unique_username, "password": "pass1234", **resp.json()}


@pytest.fixture()
def auth_headers(client, registered_user):
    resp = client.post("/auth/login", json={
        "username": registered_user["username"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# TestClient con auth + BD mockeados (para endpoints con SQL de PostgreSQL)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_user():
    user = MagicMock(spec=User)
    user.user_id = 42
    user.username = "mockuser"
    return user


@pytest.fixture()
def mock_db():
    return MagicMock()


@pytest.fixture()
def authed_client(mock_user, mock_db):
    """Cliente con get_current_user y get_db mockeados."""
    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
