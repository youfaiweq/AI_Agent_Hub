"""API registration tests for retrieval debug and evaluation."""

from fastapi.testclient import TestClient

from app.main import app


def test_retrieval_debug_and_evaluation_routes_are_documented() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/knowledge-bases/{knowledge_base_id}/retrieval/debug" in paths
    assert "/api/v1/knowledge-bases/{knowledge_base_id}/retrieval/evaluate" in paths
