"""Agent configuration, execution, and run-history service."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_handler import LLMDecisionHandler
from app.agents.runtime import AgentRuntime
from app.agents.state import AgentState, JSONValue
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.models.agent import AgentRunStatus
from app.models.agent_config import Agent
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.llms.base import LLMProvider
from app.rag.llms.openai_compatible import OpenAICompatibleLLMProvider
from app.rag.retrievers.dense import DenseRetriever
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.retrievers.sparse import SparseRetriever
from app.rag.vectorstores.qdrant import QdrantVectorStore
from app.repositories.agent_runs import AgentRunRepository, ToolCallRepository
from app.repositories.agents import AgentRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.agents import (
    AgentCreate,
    AgentResponse,
    AgentRunListResponse,
    AgentRunResponse,
    AgentUpdate,
    ToolCallResponse,
)
from app.tools.calculator import CalculatorTool
from app.tools.knowledge import KnowledgeSearchTool
from app.tools.registry import ToolRegistry
from app.tools.sql import SqlQueryTool
from app.tools.web_search import WebSearchTool, create_web_search_provider

logger = logging.getLogger(__name__)
SUPPORTED_TOOLS = {"knowledge_search", "calculator", "sql_query", "web_search"}


class AgentService:
    """Own user-scoped Agent configuration and runtime orchestration."""

    def __init__(
        self,
        session: AsyncSession,
        llm: LLMProvider | None = None,
        embedder: EmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store
        self.settings = settings or get_settings()
        self.agents = AgentRepository(session)
        self.runs = AgentRunRepository(session)
        self.tool_calls = ToolCallRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)

    async def create(self, user_id: UUID, payload: AgentCreate) -> AgentResponse:
        await self._validate_configuration(user_id, payload.knowledge_base_id, payload.tool_names)
        agent = await self.agents.create(
            user_id=user_id,
            knowledge_base_id=payload.knowledge_base_id,
            name=payload.name.strip(),
            description=payload.description,
            system_prompt=payload.system_prompt,
            model_name=payload.model_name,
            max_steps=payload.max_steps,
            timeout_seconds=payload.timeout_seconds,
            tool_names=payload.tool_names,
        )
        await self.session.commit()
        return AgentResponse.model_validate(agent)

    async def list_agents(self, user_id: UUID) -> list[AgentResponse]:
        return [AgentResponse.model_validate(item) for item in await self.agents.list_owned(user_id)]

    async def get(self, user_id: UUID, agent_id: UUID) -> Agent:
        agent = await self.agents.get_owned(agent_id, user_id)
        if agent is None:
            raise AppError("AGENT_NOT_FOUND", "Agent was not found", 404)
        return agent

    async def update(self, user_id: UUID, agent_id: UUID, payload: AgentUpdate) -> AgentResponse:
        agent = await self.get(user_id, agent_id)
        values = payload.model_dump(exclude_unset=True)
        await self._validate_configuration(
            user_id,
            values.get("knowledge_base_id", agent.knowledge_base_id),
            values.get("tool_names", agent.tool_names),
        )
        for field, value in values.items():
            setattr(agent, field, value.strip() if isinstance(value, str) else value)
        await self.session.commit()
        await self.session.refresh(agent)
        return AgentResponse.model_validate(agent)

    async def delete(self, user_id: UUID, agent_id: UUID) -> None:
        agent = await self.get(user_id, agent_id)
        await self.agents.delete(agent)
        await self.session.commit()

    async def run(self, user_id: UUID, agent_id: UUID, message: str, conversation_id: UUID | None, knowledge_base_id: UUID | None) -> AgentRunResponse:
        agent = await self.get(user_id, agent_id)
        if self.llm is None or self.embedder is None or self.vector_store is None:
            raise AppError("AGENT_RUNTIME_UNAVAILABLE", "Agent runtime dependencies are not configured", 503)
        selected_knowledge_base = knowledge_base_id or agent.knowledge_base_id
        run = await self.runs.create(
            user_id=user_id,
            agent_id=agent.id,
            conversation_id=conversation_id,
            knowledge_base_id=selected_knowledge_base,
            input_text=message,
            max_steps=agent.max_steps,
            timeout_seconds=agent.timeout_seconds,
            state={"status": "pending", "step_count": 0},
        )
        await self.session.commit()
        registry = self._build_registry(agent)
        router_llm = self.llm
        final_llm = self.llm
        if isinstance(self.llm, OpenAICompatibleLLMProvider):
            router_llm = OpenAICompatibleLLMProvider(
                settings=self.llm.settings.model_copy(
                    update={"llm_model": self.settings.agent_router_model}
                )
            )
            final_llm = OpenAICompatibleLLMProvider(
                settings=self.llm.settings.model_copy(update={"llm_model": agent.model_name})
            )
        handler = LLMDecisionHandler(
            router_llm,
            registry.list_descriptors(),
            agent.system_prompt,
            final_llm=final_llm,
            history_limit=self.settings.agent_history_max_messages,
            tool_results_limit=self.settings.agent_tool_results_max,
        )
        runtime = AgentRuntime(
            handler,
            registry,
            config=self._runtime_config(agent),
        )
        state: AgentState = {
            "messages": [{"role": "user", "content": message}],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "agent_id": agent.id,
            "agent_run_id": run.id,
            "knowledge_base_id": selected_knowledge_base,
            "tool_calls": [],
            "tool_results": [],
            "metadata": {"agent_name": agent.name, "model_name": agent.model_name},
        }
        await self.runs.update_state(
            run,
            status=AgentRunStatus.RUNNING,
            state=self._json_state(state),
            step_count=0,
        )
        await self.session.commit()
        final_state = await runtime.run(state)
        status = AgentRunStatus(final_state.get("status", "failed"))
        await self.runs.update_state(
            run,
            status=status,
            state=self._json_state(final_state),
            step_count=final_state.get("step_count", 0),
            error_code=final_state.get("error_code"),
            error_message=final_state.get("error_message"),
        )
        await self.session.commit()
        await self.session.refresh(run)
        return await self._run_response(run)

    async def list_runs(self, user_id: UUID, agent_id: UUID) -> AgentRunListResponse:
        await self.get(user_id, agent_id)
        runs = await self.runs.list_for_agent(agent_id, user_id)
        return AgentRunListResponse(items=[await self._run_response(run) for run in runs])

    async def get_run(self, user_id: UUID, agent_id: UUID, run_id: UUID) -> AgentRunResponse:
        await self.get(user_id, agent_id)
        run = await self.runs.get_owned(run_id, user_id)
        if run is None or run.agent_id != agent_id:
            raise AppError("AGENT_RUN_NOT_FOUND", "Agent run was not found", 404)
        return await self._run_response(run)

    async def _validate_configuration(self, user_id: UUID, knowledge_base_id: UUID | None, tool_names: list[str]) -> None:
        if knowledge_base_id is not None and await self.knowledge_bases.get_owned(knowledge_base_id, user_id) is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        unsupported = sorted(set(tool_names) - SUPPORTED_TOOLS)
        if unsupported:
            raise AppError("UNSUPPORTED_AGENT_TOOL", f"Unsupported Agent tools: {', '.join(unsupported)}", 422)

    def _build_registry(self, agent: Agent) -> ToolRegistry:
        dense = DenseRetriever(self.embedder, self.vector_store)
        hybrid = HybridRetriever(dense, SparseRetriever(self.session))
        registry = ToolRegistry(timeout_seconds=self.settings.tool_timeout_seconds, recorder=self.tool_calls)
        for name in agent.tool_names:
            if name == "knowledge_search":
                registry.register(KnowledgeSearchTool(hybrid))
            elif name == "calculator":
                registry.register(CalculatorTool())
            elif name == "sql_query":
                registry.register(
                    SqlQueryTool(
                        self.session,
                        settings=self.settings,
                    )
                )
            elif name == "web_search":
                registry.register(WebSearchTool(create_web_search_provider(self.settings)))
        return registry

    def _runtime_config(self, agent: Agent):
        from app.agents.contracts import AgentRuntimeConfig

        return AgentRuntimeConfig(max_steps=agent.max_steps, timeout_seconds=agent.timeout_seconds)

    async def _run_response(self, run) -> AgentRunResponse:
        state = run.state or {}
        messages = state.get("messages", [])
        answer = next(
            (item.get("content") for item in reversed(messages) if item.get("role") == "assistant"),
            None,
        )
        records = await self.tool_calls.list_for_run(run.id)
        return AgentRunResponse(
            id=run.id,
            agent_id=run.agent_id,
            conversation_id=run.conversation_id,
            knowledge_base_id=run.knowledge_base_id,
            input_text=run.input_text,
            status=run.status,
            step_count=run.step_count,
            max_steps=run.max_steps,
            timeout_seconds=run.timeout_seconds,
            answer=answer if isinstance(answer, str) else None,
            error_code=run.error_code,
            error_message=run.error_message,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            tool_calls=[
                ToolCallResponse(
                    id=record.id,
                    call_id=record.call_id,
                    tool_name=record.tool_name,
                    status=record.status,
                    arguments=record.arguments,
                    result=record.result,
                    error_code=record.error_code,
                    error_message=record.error_message,
                    duration_ms=record.duration_ms,
                    created_at=record.created_at,
                    finished_at=record.finished_at,
                )
                for record in records
            ],
        )

    @classmethod
    def _json_state(cls, state: AgentState) -> dict[str, JSONValue]:
        return cls._json_value(dict(state))  # type: ignore[return-value]

    @classmethod
    def _json_value(cls, value: object) -> JSONValue:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [cls._json_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._json_value(item) for key, item in value.items()}
        return str(value)
