"""Integration tests for document metadata and MinIO object storage."""

import logging
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.integrations.minio import MinioAdapter
from app.main import app
from app.models.user import User

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_document_upload_metadata_ownership_and_delete() -> None:
    owner_email = f"document-owner-{uuid4()}@example.com"
    other_email = f"document-other-{uuid4()}@example.com"
    password = "correct-horse-battery"
    storage_keys: list[str] = []

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def cleanup() -> None:
        async with MinioAdapter() as storage:
            for storage_key in storage_keys:
                try:
                    await storage.remove_object(storage_key)
                except Exception as exc:  # noqa: BLE001 - cleanup must continue
                    logger.warning("Document object cleanup failed: %s", type(exc).__name__)
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

            knowledge_base = await client.post(
                "/api/v1/knowledge-bases",
                headers=owner_headers,
                json={"name": "Technical Docs"},
            )
            assert knowledge_base.status_code == 201
            knowledge_base_id = knowledge_base.json()["id"]

            unsupported = await client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                headers=owner_headers,
                files={"file": ("malware.exe", b"not allowed", "application/octet-stream")},
            )
            assert unsupported.status_code == 415

            uploaded = await client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                headers=owner_headers,
                files={"file": ("guide.md", b"# AgentHub\n", "text/markdown")},
            )
            assert uploaded.status_code == 201
            document = uploaded.json()
            document_id = document["id"]
            storage_keys.append(document["storage_key"])
            assert document["filename"] == "guide.md"
            assert document["content_type"] == "text/markdown"
            assert document["size_bytes"] == 11
            assert document["status"] == "uploaded"

            processed = await client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/process",
                headers=owner_headers,
            )
            assert processed.status_code == 200
            assert processed.json()["document"]["status"] == "completed"
            assert processed.json()["chunk_count"] >= 1

            processed_again = await client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/process",
                headers=owner_headers,
            )
            assert processed_again.status_code == 200
            assert processed_again.json()["chunk_count"] == processed.json()["chunk_count"]

            listed = await client.get(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                headers=owner_headers,
            )
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
            assert listed.json()["items"][0]["id"] == document_id
            assert listed.json()["items"][0]["status"] == "completed"

            forbidden = await client.get(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
                headers=other_headers,
            )
            assert forbidden.status_code == 404

            deleted = await client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
                headers=owner_headers,
            )
            assert deleted.status_code == 204
            storage_keys.clear()

            missing = await client.get(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
                headers=owner_headers,
            )
            assert missing.status_code == 404

            broken = await client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                headers=owner_headers,
                files={"file": ("broken.pdf", b"not a PDF", "application/pdf")},
            )
            assert broken.status_code == 201
            broken_id = broken.json()["id"]
            storage_keys.append(broken.json()["storage_key"])

            failed_process = await client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{broken_id}/process",
                headers=owner_headers,
            )
            assert failed_process.status_code == 422
            failed_detail = await client.get(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{broken_id}",
                headers=owner_headers,
            )
            assert failed_detail.status_code == 200
            assert failed_detail.json()["status"] == "failed"
            assert failed_detail.json()["failure_reason"].startswith("INVALID_PDF:")

            deleted_broken = await client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{broken_id}",
                headers=owner_headers,
            )
            assert deleted_broken.status_code == 204
            storage_keys.clear()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await cleanup()
