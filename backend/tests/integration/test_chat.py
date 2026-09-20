"""Integration tests for conversations and retrieval-grounded chat."""

from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete

from app.api.v1.routes.chat import get_llm_provider
from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.integrations.minio import MinioAdapter
from app.main import app
from app.models.user import User
from app.rag.llms.base import LLMMessage, LLMProvider, LLMResponse
from app.rag.vectorstores.qdrant import QdrantVectorStore


class FakeLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0
        self.empty = False
        self.requests: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls += 1
        self.requests.append(list(messages))
        if self.empty:
            return LLMResponse(content="", model="fake")
        return LLMResponse(content="The document confirms the requested detail.", model="fake")


@pytest.mark.asyncio
async def test_conversation_chat_returns_citations_and_handles_no_context() -> None:
    email = f"chat-{uuid4()}@example.com"
    password = "correct-horse-battery"
    storage_keys: list[str] = []
    vector_documents: list[tuple[UUID, UUID]] = []
    fake_llm = FakeLLMProvider()

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def cleanup() -> None:
        async with MinioAdapter() as storage:
            for storage_key in storage_keys:
                await storage.remove_object(storage_key)
        async with QdrantVectorStore() as vector_store:
            for knowledge_base_id, document_id in vector_documents:
                await vector_store.delete_document(knowledge_base_id, document_id)
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password},
            )
            token = registered.json()["token"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            empty_kb = await client.post(
                "/api/v1/knowledge-bases",
                headers=headers,
                json={"name": "Empty Chat KB"},
            )
            assert empty_kb.status_code == 201
            empty_kb_id = empty_kb.json()["id"]
            empty_conversation = await client.post(
                "/api/v1/conversations",
                headers=headers,
                json={"knowledge_base_id": empty_kb_id, "title": "No context"},
            )
            empty_conversation_id = empty_conversation.json()["id"]
            no_context = await client.post(
                f"/api/v1/conversations/{empty_conversation_id}/chat",
                headers=headers,
                json={"message": "What does the empty knowledge base say?"},
            )
            assert no_context.status_code == 200
            assert no_context.json()["message"]["content"] == "I couldn't confirm an answer from the knowledge base."
            assert no_context.json()["citations"] == []
            assert fake_llm.calls == 0

            docs_kb = await client.post(
                "/api/v1/knowledge-bases",
                headers=headers,
                json={"name": "Chat Docs KB"},
            )
            docs_kb_id = docs_kb.json()["id"]
            uploaded = await client.post(
                f"/api/v1/knowledge-bases/{docs_kb_id}/documents",
                headers=headers,
                files={"file": ("answer.md", b"The launch date is Friday.", "text/markdown")},
            )
            document_id = uploaded.json()["id"]
            storage_keys.append(uploaded.json()["storage_key"])
            vector_documents.append((UUID(docs_kb_id), UUID(document_id)))
            processed = await client.post(
                f"/api/v1/knowledge-bases/{docs_kb_id}/documents/{document_id}/process",
                headers=headers,
            )
            assert processed.status_code == 200

            conversation = await client.post(
                "/api/v1/conversations",
                headers=headers,
                json={"knowledge_base_id": docs_kb_id, "title": "Product question"},
            )
            conversation_id = conversation.json()["id"]
            answered = await client.post(
                f"/api/v1/conversations/{conversation_id}/chat",
                headers=headers,
                json={"message": "What is the launch date?"},
            )
            assert answered.status_code == 200
            assert fake_llm.calls == 1
            assert answered.json()["message"]["content"] == "The document confirms the requested detail."
            assert answered.json()["citations"][0]["filename"] == "answer.md"

            second_answer = await client.post(
                f"/api/v1/conversations/{conversation_id}/chat",
                headers=headers,
                json={"message": "Can you repeat the launch date?"},
            )
            assert second_answer.status_code == 200
            assert fake_llm.calls == 2
            assert any(
                item.role == "user" and item.content == "What is the launch date?"
                for item in fake_llm.requests[1]
            )
            messages = await client.get(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=headers,
            )
            assert messages.status_code == 200
            assert [item["role"] for item in messages.json()["items"]] == [
                "user",
                "assistant",
                "user",
                "assistant",
            ]

            fake_llm.empty = True
            empty_response_conversation = await client.post(
                "/api/v1/conversations",
                headers=headers,
                json={"knowledge_base_id": docs_kb_id, "title": "Empty provider"},
            )
            empty_response_id = empty_response_conversation.json()["id"]
            failed = await client.post(
                f"/api/v1/conversations/{empty_response_id}/chat",
                headers=headers,
                json={"message": "What is the launch date?"},
            )
            assert failed.status_code == 502
            assert failed.json()["detail"]["code"] == "LLM_EMPTY_RESPONSE"
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_llm_provider, None)
        await cleanup()
