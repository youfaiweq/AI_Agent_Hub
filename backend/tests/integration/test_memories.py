"""Integration tests for explicit long-term memory APIs."""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_memory_extraction_requires_explicit_save_and_crud_is_user_owned() -> None:
    email = f"memory-{uuid4()}@example.com"
    other_email = f"memory-other-{uuid4()}@example.com"

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email.in_([email, other_email])))
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
            token = registered.json()["token"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            extracted = await client.post(
                "/api/v1/memories/extract",
                headers=headers,
                json={"text": "Remember that I prefer concise updates."},
            )
            assert extracted.status_code == 200
            assert extracted.json()["requires_confirmation"] is True
            candidate = extracted.json()["candidates"][0]

            before_save = await client.get("/api/v1/memories", headers=headers)
            assert before_save.status_code == 200
            assert before_save.json()["total"] == 0

            implicit = await client.post(
                "/api/v1/memories/extract",
                headers=headers,
                json={"text": "I prefer concise updates."},
            )
            assert implicit.json() == {"candidates": [], "requires_confirmation": False}

            created = await client.post(
                "/api/v1/memories",
                headers=headers,
                json={**candidate, "source": "user_confirmed", "memory_type": "preference"},
            )
            assert created.status_code == 201
            memory_id = created.json()["id"]
            assert created.json()["source"] == "user_confirmed"

            listed = await client.get(
                "/api/v1/memories",
                headers=headers,
                params={"query": "concise", "memory_type": "preference"},
            )
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
            assert listed.json()["items"][0]["id"] == memory_id

            updated = await client.patch(
                f"/api/v1/memories/{memory_id}",
                headers=headers,
                json={"content": "I prefer concise and structured updates.", "confidence": 0.9},
            )
            assert updated.status_code == 200
            assert updated.json()["confidence"] == 0.9

            other_registered = await client.post(
                "/api/v1/auth/register",
                json={"email": other_email, "password": "correct-horse-battery"},
            )
            other_headers = {
                "Authorization": f"Bearer {other_registered.json()['token']['access_token']}"
            }
            forbidden = await client.patch(
                f"/api/v1/memories/{memory_id}",
                headers=other_headers,
                json={"content": "No access"},
            )
            assert forbidden.status_code == 404

            rejected = await client.post(
                "/api/v1/memories",
                headers=headers,
                json={"content": "inferred", "source": "inferred"},
            )
            assert rejected.status_code == 422

            deleted = await client.delete(f"/api/v1/memories/{memory_id}", headers=headers)
            assert deleted.status_code == 204
            after_delete = await client.get("/api/v1/memories", headers=headers)
            assert after_delete.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await cleanup()
