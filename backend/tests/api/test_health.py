"""Tests for the v0.1 health and OpenAPI surface."""

from fastapi.testclient import TestClient

from app.main import app


def test_swagger_and_openapi_are_available() -> None:
    client = TestClient(app)

    docs_response = client.get("/docs")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    assert "/health" in openapi_response.json()["paths"]
    assert "/api/v1/system/info" in openapi_response.json()["paths"]


def test_health_reports_dependency_state(monkeypatch) -> None:
    async def fake_checks():
        from app.api.routes.health import ServiceHealth

        return {
            "postgresql": ServiceHealth(status="healthy", latency_ms=1.0),
            "redis": ServiceHealth(status="healthy", latency_ms=1.0),
            "qdrant": ServiceHealth(status="healthy", latency_ms=1.0),
            "minio": ServiceHealth(status="healthy", latency_ms=1.0),
        }

    monkeypatch.setattr("app.api.routes.health._check_dependencies", fake_checks)
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert set(response.json()["services"]) == {"postgresql", "redis", "qdrant", "minio"}
