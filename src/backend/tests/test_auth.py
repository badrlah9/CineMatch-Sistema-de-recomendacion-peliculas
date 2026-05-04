"""
Tests de integración de los endpoints de autenticación.
Usa SQLite en memoria (via fixture `client`); los routers de auth
solo usan ORM, sin SQL específico de PostgreSQL.
"""
import pytest
from jose import jwt

from app.config import get_settings

settings = get_settings()


class TestRegister:
    def test_register_success(self, client, unique_username):
        resp = client.post("/auth/register", json={
            "username": unique_username,
            "password": "pass1234",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == unique_username
        assert "user_id" in body
        assert "password_hash" not in body

    def test_register_duplicate_username_returns_409(self, client, unique_username):
        payload = {"username": unique_username, "password": "pass1234"}
        client.post("/auth/register", json=payload)
        resp = client.post("/auth/register", json=payload)
        assert resp.status_code == 409
        assert "uso" in resp.json()["detail"].lower()

    def test_register_username_too_short_returns_422(self, client):
        resp = client.post("/auth/register", json={
            "username": "ab",
            "password": "pass1234",
        })
        assert resp.status_code == 422

    def test_register_password_too_short_returns_422(self, client):
        resp = client.post("/auth/register", json={
            "username": "validuser",
            "password": "abc",
        })
        assert resp.status_code == 422

    def test_register_missing_fields_returns_422(self, client):
        resp = client.post("/auth/register", json={"username": "onlyuser"})
        assert resp.status_code == 422


class TestLogin:
    def test_login_success_returns_bearer_token(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "username": registered_user["username"],
            "password": registered_user["password"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 20

    def test_login_token_contains_user_id(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "username": registered_user["username"],
            "password": registered_user["password"],
        })
        token = resp.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == str(registered_user["user_id"])
        assert payload["username"] == registered_user["username"]

    def test_login_wrong_password_returns_401(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "username": registered_user["username"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "incorrectas" in resp.json()["detail"].lower()

    def test_login_nonexistent_user_returns_401(self, client):
        resp = client.post("/auth/login", json={
            "username": "ghost_user_xyz",
            "password": "pass1234",
        })
        assert resp.status_code == 401

    def test_login_same_message_for_wrong_user_and_wrong_pass(self, client, registered_user):
        """Seguridad: mismo mensaje de error tanto si el usuario no existe
        como si la contraseña es incorrecta (evita user enumeration)."""
        resp_bad_user = client.post("/auth/login", json={
            "username": "ghost_user_xyz", "password": "pass1234",
        })
        resp_bad_pass = client.post("/auth/login", json={
            "username": registered_user["username"], "password": "badpass",
        })
        assert resp_bad_user.json()["detail"] == resp_bad_pass.json()["detail"]

    def test_login_missing_password_returns_422(self, client, registered_user):
        resp = client.post("/auth/login", json={"username": registered_user["username"]})
        assert resp.status_code == 422


class TestProtectedEndpoints:
    def test_request_without_token_returns_401(self, client):
        resp = client.get("/ratings/me")
        assert resp.status_code == 401

    def test_request_with_invalid_token_returns_401(self, client):
        resp = client.get("/ratings/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_valid_token_allows_access(self, client, auth_headers):
        # DELETE /users/me/preferences usa solo ORM → funciona con SQLite
        resp = client.delete("/users/me/preferences", headers=auth_headers)
        assert resp.status_code == 204
