"""Tests for the version 1 system endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_system_info_returns_public_application_metadata() -> None:
    response = TestClient(app).get("/api/v1/system/info")

    assert response.status_code == 200
    assert response.json() == {
        "name": "AgentHub",
        "version": "0.2.0",
        "environment": "development",
    }


def test_cors_preflight_is_available_for_development_frontend() -> None:
    response = TestClient(app).options(
        "/api/v1/system/info",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
