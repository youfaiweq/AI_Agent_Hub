"""Integration tests for user-owned Agent configuration APIs."""

import httpx
import pytest
from sqlalchemy import delete

from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_agent_configuration_crud_is_user_owned() -> None:
    email = "agent-config-owner@example.com"

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "correct-horse-battery"},
            )
            assert registered.status_code == 201
            headers = {"Authorization": f"Bearer {registered.json()['token']['access_token']}"}

            created = await client.post(
                "/api/v1/agents",
                headers=headers,
                json={
                    "name": "Research assistant",
                    "description": "Uses safe read-only tools",
                    "tool_names": ["calculator"],
                    "max_steps": 3,
                },
            )
            assert created.status_code == 201
            agent_id = created.json()["id"]
            assert created.json()["tool_names"] == ["calculator"]

            listed = await client.get("/api/v1/agents", headers=headers)
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == agent_id

            updated = await client.patch(
                f"/api/v1/agents/{agent_id}",
                headers=headers,
                json={"name": "Updated assistant"},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Updated assistant"

            runs = await client.get(f"/api/v1/agents/{agent_id}/runs", headers=headers)
            assert runs.status_code == 200
            assert runs.json()["items"] == []

            deleted = await client.delete(f"/api/v1/agents/{agent_id}", headers=headers)
            assert deleted.status_code == 204
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await cleanup()
