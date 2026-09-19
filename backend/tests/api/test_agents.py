"""API registration tests for Agent configuration and runtime endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_agent_api_routes_are_documented() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/agents" in paths
    assert "/api/v1/agents/{agent_id}" in paths
    assert "/api/v1/agents/{agent_id}/runs" in paths
    assert "/api/v1/agents/{agent_id}/runs/{run_id}" in paths
