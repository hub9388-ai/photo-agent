from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["legacy"]["agentCodeOnPath"] is True
    assert payload["service"]["name"]
