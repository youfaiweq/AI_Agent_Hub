"""Agent configuration, execution, and run-history service."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_handler import LLMDecisionHandler
from app.agents.runtime import AgentRuntime
from app.agents.state import AgentState, JSONValue
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.memory.short_term import MemoryMessage, ShortTermMemory
from app.models.agent import AgentApproval, AgentRunStatus, ApprovalStatus
from app.models.agent_config import Agent
from app.observability import (
    NoopObservabilityAdapter,
    ObservabilityAdapter,
    ObservedLLMProvider,
    new_trace_id,
    observe,
)
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.llms.base import LLMProvider
from app.rag.llms.openai_compatible import OpenAICompatibleLLMProvider
from app.rag.retrievers.dense import DenseRetriever
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.retrievers.sparse import SparseRetriever
from app.rag.vectorstores.qdrant import QdrantVectorStore
from app.repositories.agent_runs import AgentRunRepository, ToolCallRepository
from app.repositories.agents import AgentRepository
from app.repositories.approvals import ApprovalRepository
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.agents import (
    AgentCreate,
    AgentResponse,
    AgentRunListResponse,
    AgentRunResponse,
    AgentUpdate,
    ApprovalResponse,
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
        observability: ObservabilityAdapter | None = None,
    ) -> None:
        self.session = session
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store
        self.settings = settings or get_settings()
        self.observability = observability or NoopObservabilityAdapter()
        self.agents = AgentRepository(session)
        self.runs = AgentRunRepository(session)
        self.tool_calls = ToolCallRepository(session)
        self.approvals = ApprovalRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

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
        trace_id = new_trace_id()
        conversation_history: list[MemoryMessage] = []
        if conversation_id is not None:
            conversation = await self.conversations.get_owned(conversation_id, user_id)
            if conversation is None:
                raise AppError("CONVERSATION_NOT_FOUND", "Conversation was not found", 404)
            if knowledge_base_id is None and agent.knowledge_base_id is None:
                knowledge_base_id = conversation.knowledge_base_id
            async with observe(
                self.observability,
                kind="memory",
                name="short_term.load",
                trace_id=trace_id,
                metadata={"max_messages": self.settings.agent_history_max_messages},
            ):
                history_records = await self.messages.list_for_conversation(
                    conversation.id,
                    limit=self.settings.agent_history_max_messages,
                )
                memory = ShortTermMemory(
                    max_messages=self.settings.agent_history_max_messages,
                    token_budget=self.settings.agent_context_token_budget,
                )
                conversation_history = list(
                    memory.select(
                        [
                            MemoryMessage(role=item.role, content=item.content)
                            for item in history_records
                            if item.role in {"user", "assistant"}
                        ]
                    ).messages
                )
            await self.messages.create(conversation.id, "user", message)
            self.conversations.touch(conversation)
            await self.session.commit()
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
        state: AgentState = {
            "messages": [
                {"role": item.role, "content": item.content} for item in conversation_history
            ]
            + [{"role": "user", "content": message}],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "agent_id": agent.id,
            "agent_run_id": run.id,
            "knowledge_base_id": selected_knowledge_base,
            "tool_calls": [],
            "tool_results": [],
            "metadata": {
                "agent_name": agent.name,
                "model_name": agent.model_name,
                "trace_id": trace_id,
            },
        }
        await self.runs.update_state(
            run,
            status=AgentRunStatus.RUNNING,
            state=self._json_state(state),
            step_count=0,
        )
        await self.session.commit()
        final_state = await self._execute_runtime(agent, state)
        return await self._persist_runtime_result(user_id, agent, run, final_state)

    async def approve(self, user_id: UUID, agent_id: UUID, run_id: UUID) -> AgentRunResponse:
        run, _ = await self._get_owned_run(user_id, agent_id, run_id)
        approval = await self.approvals.get_for_run(run.id)
        if approval is None:
            raise AppError("APPROVAL_NOT_FOUND", "Approval request was not found", 404)
        if approval.status == ApprovalStatus.PENDING:
            if self._is_expired(approval):
                return await self._expire_approval(user_id, run, approval)
            await self.approvals.update_status(approval, ApprovalStatus.APPROVED)
            await self.session.commit()
        elif approval.status != ApprovalStatus.APPROVED:
            raise AppError("APPROVAL_ALREADY_DECIDED", "Approval request was already decided", 409)
        return await self.resume(user_id, agent_id, run_id)

    async def reject(self, user_id: UUID, agent_id: UUID, run_id: UUID) -> AgentRunResponse:
        run, _ = await self._get_owned_run(user_id, agent_id, run_id)
        approval = await self.approvals.get_for_run(run.id)
        if approval is None:
            raise AppError("APPROVAL_NOT_FOUND", "Approval request was not found", 404)
        if approval.status == ApprovalStatus.PENDING:
            if self._is_expired(approval):
                return await self._expire_approval(user_id, run, approval)
            await self.approvals.update_status(approval, ApprovalStatus.REJECTED)
            await self._finish_rejected_run(run, approval, "APPROVAL_REJECTED", "Tool approval was rejected")
            await self.session.commit()
            return await self._run_response(run)
        if approval.status == ApprovalStatus.REJECTED:
            return await self._run_response(run)
        raise AppError("APPROVAL_ALREADY_DECIDED", "Approval request was already decided", 409)

    async def resume(self, user_id: UUID, agent_id: UUID, run_id: UUID) -> AgentRunResponse:
        run, agent = await self._get_owned_run(user_id, agent_id, run_id)
        approval = await self.approvals.get_for_run(run.id)
        if approval is None:
            raise AppError("APPROVAL_NOT_FOUND", "Approval request was not found", 404)
        if approval.status == ApprovalStatus.PENDING:
            if self._is_expired(approval):
                return await self._expire_approval(user_id, run, approval)
            raise AppError("APPROVAL_REQUIRED", "Approve the pending tool call before resuming", 409)
        if approval.status != ApprovalStatus.APPROVED:
            return await self._run_response(run)
        if run.status != AgentRunStatus.WAITING_APPROVAL:
            return await self._run_response(run)
        state = AgentState(**(run.state or {}))
        state["approved_tool_call_id"] = approval.call_id
        state["resume_approval"] = True
        request = dict(state.get("approval_request") or {})
        request["status"] = ApprovalStatus.APPROVED
        state["approval_request"] = request
        await self.runs.update_state(
            run,
            status=AgentRunStatus.RUNNING,
            state=self._json_state(state),
            step_count=run.step_count,
            error_code=None,
            error_message=None,
        )
        await self.session.commit()
        final_state = await self._execute_runtime(agent, state)
        return await self._persist_runtime_result(user_id, agent, run, final_state)

    async def list_runs(self, user_id: UUID, agent_id: UUID) -> AgentRunListResponse:
        await self.get(user_id, agent_id)
        runs = await self.runs.list_for_agent(agent_id, user_id)
        return AgentRunListResponse(items=[await self._run_response(run) for run in runs])

    async def get_run(self, user_id: UUID, agent_id: UUID, run_id: UUID) -> AgentRunResponse:
        run, _ = await self._get_owned_run(user_id, agent_id, run_id)
        return await self._run_response(run)

    async def _get_owned_run(self, user_id: UUID, agent_id: UUID, run_id: UUID):
        agent = await self.get(user_id, agent_id)
        run = await self.runs.get_owned(run_id, user_id)
        if run is None or run.agent_id != agent_id:
            raise AppError("AGENT_RUN_NOT_FOUND", "Agent run was not found", 404)
        return run, agent

    async def _execute_runtime(self, agent: Agent, state: AgentState) -> AgentState:
        if self.llm is None or self.embedder is None or self.vector_store is None:
            raise AppError("AGENT_RUNTIME_UNAVAILABLE", "Agent runtime dependencies are not configured", 503)
        trace_id = str(state.get("metadata", {}).get("trace_id") or new_trace_id())
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
        router_llm = ObservedLLMProvider(
            router_llm,
            self.observability,
            trace_id=trace_id,
            name="agent.router.generate",
        )
        final_llm = ObservedLLMProvider(
            final_llm,
            self.observability,
            trace_id=trace_id,
            name="agent.final.generate",
        )
        handler = LLMDecisionHandler(
            router_llm,
            registry.list_descriptors(),
            agent.system_prompt,
            final_llm=final_llm,
            history_limit=self.settings.agent_history_max_messages,
            context_token_budget=self.settings.agent_context_token_budget,
            tool_results_limit=self.settings.agent_tool_results_max,
        )
        runtime = AgentRuntime(handler, registry, config=self._runtime_config(agent))
        async with (
            observe(
                self.observability,
                kind="trace",
                name="agent",
                trace_id=trace_id,
                metadata={"agent_id": str(agent.id)},
            ),
            observe(
                self.observability,
                kind="agent_run",
                name=agent.name,
                trace_id=trace_id,
                model=agent.model_name,
                metadata={"max_steps": agent.max_steps},
            ),
        ):
            return await runtime.run(state)

    async def _persist_runtime_result(
        self,
        user_id: UUID,
        agent: Agent,
        run,
        final_state: AgentState,
    ) -> AgentRunResponse:
        status = AgentRunStatus(final_state.get("status", "failed"))
        if status == AgentRunStatus.WAITING_APPROVAL:
            request = final_state.get("approval_request")
            if not isinstance(request, dict):
                status = AgentRunStatus.FAILED
                final_state["status"] = status
                final_state["error_code"] = "APPROVAL_REQUEST_MISSING"
                final_state["error_message"] = "Agent approval request was incomplete"
            else:
                expires_at = datetime.now(UTC) + timedelta(
                    seconds=self.settings.agent_approval_timeout_seconds
                )
                approval = await self.approvals.create(
                    agent_run_id=run.id,
                    call_id=str(request.get("tool_call_id", "")),
                    tool_name=str(request.get("tool_name", "")),
                    arguments=request.get("arguments") if isinstance(request.get("arguments"), dict) else {},
                    expires_at=expires_at,
                )
                request = dict(request)
                request["approval_id"] = str(approval.id)
                request["expires_at"] = expires_at.isoformat()
                final_state["approval_request"] = request
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
        if run.conversation_id is not None and status == AgentRunStatus.COMPLETED:
            answer = next(
                (
                    item.get("content")
                    for item in reversed(final_state.get("messages", []))
                    if item.get("role") == "assistant"
                ),
                None,
            )
            if isinstance(answer, str) and answer.strip():
                await self.messages.create(run.conversation_id, "assistant", answer.strip())
                conversation = await self.conversations.get_owned(run.conversation_id, user_id)
                if conversation is not None:
                    self.conversations.touch(conversation)
                await self.session.commit()
        return await self._run_response(run)

    async def _expire_approval(self, user_id: UUID, run, approval: AgentApproval) -> AgentRunResponse:
        await self.approvals.update_status(approval, ApprovalStatus.EXPIRED)
        await self._finish_rejected_run(run, approval, "APPROVAL_EXPIRED", "Tool approval expired")
        await self.session.commit()
        return await self._run_response(run)

    async def _finish_rejected_run(
        self,
        run,
        approval: AgentApproval,
        error_code: str,
        error_message: str,
    ) -> None:
        state = dict(run.state or {})
        request = dict(state.get("approval_request") or {})
        request["status"] = approval.status
        state["approval_request"] = request
        state["resume_approval"] = False
        state["status"] = AgentRunStatus.FAILED
        state["error_code"] = error_code
        state["error_message"] = error_message
        record = await self.tool_calls.get_for_run_call(run.id, approval.call_id)
        if record is not None:
            await self.tool_calls.update_status(
                record,
                status="failed",
                error_code=error_code,
                error_message=error_message,
            )
        await self.runs.update_state(
            run,
            status=AgentRunStatus.FAILED,
            state=self._json_state(AgentState(**state)),
            step_count=run.step_count,
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    def _is_expired(approval: AgentApproval) -> bool:
        expires_at = approval.expires_at
        if isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            return expires_at <= datetime.now(UTC)
        return False

    async def _validate_configuration(self, user_id: UUID, knowledge_base_id: UUID | None, tool_names: list[str]) -> None:
        if knowledge_base_id is not None and await self.knowledge_bases.get_owned(knowledge_base_id, user_id) is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        unsupported = sorted(set(tool_names) - SUPPORTED_TOOLS)
        if unsupported:
            raise AppError("UNSUPPORTED_AGENT_TOOL", f"Unsupported Agent tools: {', '.join(unsupported)}", 422)

    def _build_registry(self, agent: Agent) -> ToolRegistry:
        dense = DenseRetriever(self.embedder, self.vector_store)
        hybrid = HybridRetriever(dense, SparseRetriever(self.session))
        registry = ToolRegistry(
            timeout_seconds=self.settings.tool_timeout_seconds,
            recorder=self.tool_calls,
            observability=self.observability,
        )
        for name in agent.tool_names:
            if name == "knowledge_search":
                registry.register(KnowledgeSearchTool(hybrid, observability=self.observability))
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
        approval = await self.approvals.get_for_run(run.id)
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
            approval=(
                ApprovalResponse(
                    id=approval.id,
                    agent_run_id=approval.agent_run_id,
                    call_id=approval.call_id,
                    tool_name=approval.tool_name,
                    arguments=approval.arguments,
                    status=approval.status,
                    expires_at=approval.expires_at,
                    decided_at=approval.decided_at,
                )
                if approval is not None
                else None
            ),
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
