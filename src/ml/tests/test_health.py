"""
Test: Health Endpoint

Qué comprueba:
- Que la API del servicio ML está levantada
- Que el endpoint /health responde correctamente
- Que devuelve los campos básicos de estado (ok, service, ready, model_version)

Objetivo:
Detectar rápidamente si la API está caída o mal inicializada.
"""




from fastapi.testclient import TestClient

from fastapi_app import app


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["ok"] is True
    assert data["service"] == "CineMatch"
    assert "model_version" in data
    assert "ready" in data