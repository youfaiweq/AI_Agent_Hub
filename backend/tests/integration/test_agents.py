"""Integration tests for user-owned Agent configuration APIs."""

import httpx
import pytest
from sqlalchemy import delete

from app.agents.state import JSONValue
from app.api.v1.routes.agents import get_agent_runtime_service
from app.core.config import get_settings
from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.core.dependencies import SessionDependency
from app.main import app
from app.models.user import User
from app.rag.llms.base import LLMMessage, LLMProvider, LLMResponse
from app.services.agents import AgentService
from app.tools.registry import BaseTool, ToolContext, ToolRegistry


class ConversationAgentLLM(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        self.requests.append(list(messages))
        return LLMResponse(content='{"action":"answer","content":"Conversation answer"}', model="fake")


class ApprovalAgentLLM(LLMProvider):
    def __init__(self) -> None:
        self.responses = [
            '{"action":"tool","name":"send_notification","arguments":{"message":"hello"}}',
            '{"action":"answer","content":"Notification sent"}',
            '{"action":"tool","name":"send_notification","arguments":{"message":"reject"}}',
        ]

    async def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        return LLMResponse(content=self.responses.pop(0), model="fake")


class DangerousNotificationTool(BaseTool):
    executions = 0

    @property
    def name(self) -> str:
        return "send_notification"

    @property
    def description(self) -> str:
        return "Send an external notification."

    @property
    def input_schema(self) -> dict[str, JSONValue]:
        return {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }

    @property
    def requires_approval(self) -> bool:
        return True

    async def execute(self, arguments: dict[str, JSONValue], context: ToolContext) -> JSONValue:
        type(self).executions += 1
        return {"sent": arguments["message"]}


class ApprovalAgentService(AgentService):
    def _build_registry(self, agent) -> ToolRegistry:
        registry = ToolRegistry(timeout_seconds=self.settings.tool_timeout_seconds, recorder=self.tool_calls)
        registry.register(DangerousNotificationTool())
        return registry


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


@pytest.mark.asyncio
async def test_agent_run_loads_and_persists_short_term_conversation_memory() -> None:
    email = "agent-memory@example.com"
    fake_llm = ConversationAgentLLM()

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def override_runtime_service(session: SessionDependency) -> AgentService:
        return AgentService(
            session,
            llm=fake_llm,
            embedder=object(),
            vector_store=object(),
            settings=get_settings(),
        )

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_agent_runtime_service] = override_runtime_service
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "correct-horse-battery"},
            )
            headers = {"Authorization": f"Bearer {registered.json()['token']['access_token']}"}
            knowledge_base = await client.post(
                "/api/v1/knowledge-bases",
                headers=headers,
                json={"name": "Agent memory KB"},
            )
            knowledge_base_id = knowledge_base.json()["id"]
            conversation = await client.post(
                "/api/v1/conversations",
                headers=headers,
                json={"knowledge_base_id": knowledge_base_id, "title": "Agent memory"},
            )
            conversation_id = conversation.json()["id"]
            agent = await client.post(
                "/api/v1/agents",
                headers=headers,
                json={"name": "Memory agent", "tool_names": ["calculator"]},
            )
            agent_id = agent.json()["id"]

            first = await client.post(
                f"/api/v1/agents/{agent_id}/runs",
                headers=headers,
                json={"message": "Remember this turn", "conversation_id": conversation_id},
            )
            assert first.status_code == 200
            second = await client.post(
                f"/api/v1/agents/{agent_id}/runs",
                headers=headers,
                json={"message": "Use the previous turn", "conversation_id": conversation_id},
            )
            assert second.status_code == 200
            assert any(
                item.role == "user" and item.content == "Remember this turn"
                for item in fake_llm.requests[1]
            )

            messages = await client.get(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=headers,
            )
            assert [item["role"] for item in messages.json()["items"]] == [
                "user",
                "assistant",
                "user",
                "assistant",
            ]
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_agent_runtime_service, None)
        await cleanup()


@pytest.mark.asyncio
async def test_agent_approval_api_approves_rejects_and_is_idempotent() -> None:
    email = "agent-approval@example.com"
    fake_llm = ApprovalAgentLLM()

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def override_runtime_service(session: SessionDependency) -> AgentService:
        return ApprovalAgentService(
            session,
            llm=fake_llm,
            embedder=object(),
            vector_store=object(),
            settings=get_settings(),
        )

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_agent_runtime_service] = override_runtime_service
    DangerousNotificationTool.executions = 0
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "correct-horse-battery"},
            )
            headers = {"Authorization": f"Bearer {registered.json()['token']['access_token']}"}
            agent = await client.post(
                "/api/v1/agents",
                headers=headers,
                json={"name": "Approval agent", "tool_names": ["calculator"]},
            )
            agent_id = agent.json()["id"]

            waiting = await client.post(
                f"/api/v1/agents/{agent_id}/runs",
                headers=headers,
                json={"message": "Send hello"},
            )
            assert waiting.status_code == 200
            run_id = waiting.json()["id"]
            assert waiting.json()["status"] == "waiting_approval"
            assert waiting.json()["approval"]["status"] == "pending"
            assert DangerousNotificationTool.executions == 0

            approved = await client.post(
                f"/api/v1/agents/{agent_id}/runs/{run_id}/approve",
                headers=headers,
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "completed"
            assert approved.json()["approval"]["status"] == "approved"
            assert DangerousNotificationTool.executions == 1

            repeated_approve = await client.post(
                f"/api/v1/agents/{agent_id}/runs/{run_id}/approve",
                headers=headers,
            )
            assert repeated_approve.status_code == 200
            assert repeated_approve.json()["status"] == "completed"
            assert DangerousNotificationTool.executions == 1

            waiting_reject = await client.post(
                f"/api/v1/agents/{agent_id}/runs",
                headers=headers,
                json={"message": "Send reject"},
            )
            reject_run_id = waiting_reject.json()["id"]
            rejected = await client.post(
                f"/api/v1/agents/{agent_id}/runs/{reject_run_id}/reject",
                headers=headers,
            )
            assert rejected.status_code == 200
            assert rejected.json()["status"] == "failed"
            assert rejected.json()["error_code"] == "APPROVAL_REJECTED"
            repeated_reject = await client.post(
                f"/api/v1/agents/{agent_id}/runs/{reject_run_id}/reject",
                headers=headers,
            )
            assert repeated_reject.status_code == 200
            assert repeated_reject.json()["error_code"] == "APPROVAL_REJECTED"
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_agent_runtime_service, None)
        await cleanup()


@pytest.mark.asyncio
async def test_agent_approval_expires_to_failed_terminal_state() -> None:
    email = "agent-approval-expired@example.com"
    fake_llm = ApprovalAgentLLM()

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def override_runtime_service(session: SessionDependency) -> AgentService:
        settings = get_settings().model_copy(update={"agent_approval_timeout_seconds": -1.0})
        return ApprovalAgentService(
            session,
            llm=fake_llm,
            embedder=object(),
            vector_store=object(),
            settings=settings,
        )

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_agent_runtime_service] = override_runtime_service
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "correct-horse-battery"},
            )
            headers = {"Authorization": f"Bearer {registered.json()['token']['access_token']}"}
            agent = await client.post(
                "/api/v1/agents",
                headers=headers,
                json={"name": "Expiring approval agent", "tool_names": ["calculator"]},
            )
            agent_id = agent.json()["id"]
            waiting = await client.post(
                f"/api/v1/agents/{agent_id}/runs",
                headers=headers,
                json={"message": "This will expire"},
            )
            expired = await client.post(
                f"/api/v1/agents/{agent_id}/runs/{waiting.json()['id']}/approve",
                headers=headers,
            )
            assert expired.status_code == 200
            assert expired.json()["status"] == "failed"
            assert expired.json()["error_code"] == "APPROVAL_EXPIRED"
            assert expired.json()["approval"]["status"] == "expired"
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_agent_runtime_service, None)
        await cleanup()
