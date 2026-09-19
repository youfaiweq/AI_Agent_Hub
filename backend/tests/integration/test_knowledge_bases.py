"""Integration tests for knowledge base CRUD and ownership boundaries."""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_knowledge_base_crud_is_user_scoped() -> None:
    owner_email = f"kb-owner-{uuid4()}@example.com"
    other_email = f"kb-other-{uuid4()}@example.com"
    password = "correct-horse-battery"

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email.in_([owner_email, other_email])))
            await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            owner_register = await client.post(
                "/api/v1/auth/register",
                json={"email": owner_email, "password": password},
            )
            other_register = await client.post(
                "/api/v1/auth/register",
                json={"email": other_email, "password": password},
            )
            assert owner_register.status_code == 201
            assert other_register.status_code == 201
            owner_token = owner_register.json()["token"]["access_token"]
            other_token = other_register.json()["token"]["access_token"]
            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            other_headers = {"Authorization": f"Bearer {other_token}"}

            created = await client.post(
                "/api/v1/knowledge-bases",
                headers=owner_headers,
                json={"name": " Product Docs ", "description": "Initial description"},
            )
            assert created.status_code == 201
            knowledge_base_id = created.json()["id"]
            assert created.json()["name"] == "Product Docs"

            second = await client.post(
                "/api/v1/knowledge-bases",
                headers=owner_headers,
                json={"name": "Support FAQ"},
            )
            assert second.status_code == 201

            listed = await client.get(
                "/api/v1/knowledge-bases?page=1&page_size=1&sort_by=name&sort_order=asc",
                headers=owner_headers,
            )
            assert listed.status_code == 200
            assert listed.json()["total"] == 2
            assert len(listed.json()["items"]) == 1
            assert listed.json()["items"][0]["name"] == "Product Docs"

            forbidden_read = await client.get(
                f"/api/v1/knowledge-bases/{knowledge_base_id}",
                headers=other_headers,
            )
            assert forbidden_read.status_code == 404

            updated = await client.patch(
                f"/api/v1/knowledge-bases/{knowledge_base_id}",
                headers=owner_headers,
                json={"description": "Updated description"},
            )
            assert updated.status_code == 200
            assert updated.json()["description"] == "Updated description"

            forbidden_delete = await client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}",
                headers=other_headers,
            )
            assert forbidden_delete.status_code == 404

            deleted = await client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}",
                headers=owner_headers,
            )
            assert deleted.status_code == 204
            deleted_lookup = await client.get(
                f"/api/v1/knowledge-bases/{knowledge_base_id}",
                headers=owner_headers,
            )
            assert deleted_lookup.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await cleanup()
