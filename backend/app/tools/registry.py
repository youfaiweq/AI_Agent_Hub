"""Provider-neutral Tool Registry and execution adapter."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol
from uuid import UUID

from app.agents.contracts import ToolExecutionResult
from app.agents.state import AgentState, JSONValue, ToolCallState
from app.observability import ObservabilityAdapter, ObservationEvent, new_trace_id, safe_emit

logger = logging.getLogger(__name__)


class ToolRegistryError(ValueError):
    """Invalid registry configuration or registration operation."""


class ToolError(RuntimeError):
    """Structured error raised by a tool during execution."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class ToolContext:
    """Domain context passed to a tool without coupling it to FastAPI."""

    user_id: UUID | None
    conversation_id: UUID | None
    agent_id: UUID | None
    knowledge_base_id: UUID | None
    metadata: dict[str, JSONValue]

    @classmethod
    def from_state(cls, state: AgentState) -> "ToolContext":
        return cls(
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            agent_id=state.get("agent_id"),
            knowledge_base_id=state.get("knowledge_base_id"),
            metadata=dict(state.get("metadata", {})),
        )


@dataclass(frozen=True)
class ToolDescriptor:
    """Safe tool metadata exposed to an Agent planner or UI."""

    name: str
    description: str
    input_schema: dict[str, JSONValue]
    requires_approval: bool = False


class BaseTool(ABC):
    """Contract every concrete tool must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable tool name used in Agent tool calls."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a planner-facing description."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, JSONValue]:
        """Return a JSON-schema-like object input contract."""

    @property
    def requires_approval(self) -> bool:
        """Return whether this tool must wait for explicit user approval."""

        return False

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, JSONValue],
        context: ToolContext,
    ) -> JSONValue:
        """Execute the tool with validated arguments and domain context."""


class ToolCallRecorder(Protocol):
    """Persistence subset required by the registry."""

    async def create(self, **kwargs: object) -> object: ...

    async def update_status(self, record: object, **kwargs: object) -> object: ...

    async def get_for_run_call(self, agent_run_id: UUID, call_id: str) -> object | None: ...


class ToolRegistry:
    """Register tools and execute them with validation, timeout, and audit hooks."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        recorder: ToolCallRecorder | None = None,
        observability: ObservabilityAdapter | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ToolRegistryError("timeout_seconds must be greater than zero")
        self.timeout_seconds = timeout_seconds
        self.recorder = recorder
        self.observability = observability
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        descriptor = self._descriptor_for(tool)
        if descriptor.name in self._tools:
            raise ToolRegistryError(f"Tool is already registered: {descriptor.name}")
        self._tools[descriptor.name] = tool

    def get_descriptor(self, name: str) -> ToolDescriptor:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError("TOOL_NOT_FOUND", f"Tool is not registered: {name}")
        return self._descriptor_for(tool)

    def list_descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(
            self._descriptor_for(self._tools[name]) for name in sorted(self._tools)
        )

    async def execute(
        self,
        tool_call: ToolCallState,
        state: AgentState,
    ) -> ToolExecutionResult:
        started = perf_counter()
        call_id = str(tool_call.get("call_id", ""))
        tool_name = str(tool_call.get("name", ""))
        record = None
        try:
            arguments = tool_call.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ToolError("TOOL_INVALID_INPUT", "Tool arguments must be an object")
            record = await self._resume_record(state, call_id)
            if record is None:
                record = await self._start_record(state, call_id, tool_name, arguments)
            await self._mark_record_running(record)
            tool = self._tools.get(tool_name)
            if tool is None:
                raise ToolError("TOOL_NOT_FOUND", f"Tool is not registered: {tool_name}")
            self._validate_arguments(tool.input_schema, arguments)
            if tool.requires_approval and state.get("approved_tool_call_id") != call_id:
                approval_message = f"Approval required before executing tool: {tool_name}"
                await self._finish_record(
                    record,
                    "waiting_approval",
                    error_code="TOOL_APPROVAL_REQUIRED",
                    error_message=approval_message,
                )
                await self._emit_observation(
                    state,
                    call_id,
                    tool_name,
                    "waiting_approval",
                    started,
                    error_code="TOOL_APPROVAL_REQUIRED",
                )
                return ToolExecutionResult(
                    approval_required=True,
                    approval_message=approval_message,
                )
            async with asyncio.timeout(self.timeout_seconds):
                result = await tool.execute(arguments, ToolContext.from_state(state))
            duration_ms = round((perf_counter() - started) * 1000, 2)
            await self._finish_record(record, "completed", result=result, duration_ms=duration_ms)
            await self._emit_observation(
                state,
                call_id,
                tool_name,
                "completed",
                started,
            )
            logger.info(
                "Tool execution completed",
                extra={"tool_name": tool_name, "call_id": call_id, "duration_ms": duration_ms},
            )
            return ToolExecutionResult(result=result)
        except ToolError as exc:
            duration_ms = round((perf_counter() - started) * 1000, 2)
            await self._finish_record(
                record,
                "failed",
                error_code=exc.code,
                error_message=exc.message,
                duration_ms=duration_ms,
            )
            await self._emit_observation(state, call_id, tool_name, "failed", started, error_code=exc.code)
            logger.warning(
                "Tool execution failed",
                extra={"tool_name": tool_name, "call_id": call_id, "error_code": exc.code},
            )
            return ToolExecutionResult(error_code=exc.code, error_message=exc.message)
        except TimeoutError:
            duration_ms = round((perf_counter() - started) * 1000, 2)
            await self._finish_record(
                record,
                "failed",
                error_code="TOOL_TIMEOUT",
                error_message="Tool execution timed out",
                duration_ms=duration_ms,
            )
            await self._emit_observation(state, call_id, tool_name, "failed", started, error_code="TOOL_TIMEOUT")
            logger.warning(
                "Tool execution timed out",
                extra={"tool_name": tool_name, "call_id": call_id},
            )
            return ToolExecutionResult(
                error_code="TOOL_TIMEOUT",
                error_message="Tool execution timed out",
            )
        except Exception:
            duration_ms = round((perf_counter() - started) * 1000, 2)
            await self._finish_record(
                record,
                "failed",
                error_code="TOOL_EXECUTION_FAILED",
                error_message="Tool execution failed",
                duration_ms=duration_ms,
            )
            await self._emit_observation(
                state,
                call_id,
                tool_name,
                "failed",
                started,
                error_code="TOOL_EXECUTION_FAILED",
            )
            logger.exception(
                "Unexpected tool execution failure",
                extra={"tool_name": tool_name, "call_id": call_id},
            )
            return ToolExecutionResult(
                error_code="TOOL_EXECUTION_FAILED",
                error_message="Tool execution failed",
            )

    @staticmethod
    def _descriptor_for(tool: BaseTool) -> ToolDescriptor:
        name = tool.name.strip()
        if not name:
            raise ToolRegistryError("Tool name must not be empty")
        description = tool.description.strip()
        if not description:
            raise ToolRegistryError(f"Tool description must not be empty: {name}")
        schema = tool.input_schema
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ToolRegistryError(f"Tool input_schema must describe an object: {name}")
        return ToolDescriptor(
            name=name,
            description=description,
            input_schema=schema,
            requires_approval=tool.requires_approval,
        )

    @staticmethod
    def _validate_arguments(
        schema: dict[str, JSONValue],
        arguments: dict[str, JSONValue],
    ) -> None:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise ToolError("TOOL_INVALID_SCHEMA", "Tool input_schema is malformed")
        missing = [name for name in required if isinstance(name, str) and name not in arguments]
        if missing:
            raise ToolError("TOOL_INVALID_INPUT", f"Missing required tool arguments: {', '.join(missing)}")
        for name, value in arguments.items():
            definition = properties.get(name)
            if definition is None:
                raise ToolError("TOOL_INVALID_INPUT", f"Unknown tool argument: {name}")
            if not isinstance(definition, dict):
                raise ToolError("TOOL_INVALID_SCHEMA", f"Tool argument schema is malformed: {name}")
            expected_type = definition.get("type")
            if not ToolRegistry._matches_type(value, expected_type):
                raise ToolError("TOOL_INVALID_INPUT", f"Invalid type for tool argument: {name}")

    @staticmethod
    def _matches_type(value: JSONValue, expected_type: object) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        return False

    async def _start_record(
        self,
        state: AgentState,
        call_id: str,
        tool_name: str,
        arguments: dict[str, JSONValue],
    ) -> object | None:
        if self.recorder is None or state.get("agent_run_id") is None:
            return None
        return await self.recorder.create(
            agent_run_id=state["agent_run_id"],
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        )

    async def _resume_record(self, state: AgentState, call_id: str) -> object | None:
        if self.recorder is None or state.get("agent_run_id") is None:
            return None
        if not state.get("resume_approval"):
            return None
        get_record = getattr(self.recorder, "get_for_run_call", None)
        if get_record is None:
            return None
        return await get_record(state["agent_run_id"], call_id)

    async def _emit_observation(
        self,
        state: AgentState,
        call_id: str,
        tool_name: str,
        status: str,
        started: float,
        *,
        error_code: str | None = None,
    ) -> None:
        if self.observability is None:
            return
        from datetime import UTC, datetime

        trace_id = state.get("metadata", {}).get("trace_id")
        await safe_emit(
            self.observability,
            ObservationEvent(
                kind="tool",
                name=tool_name,
                trace_id=trace_id if isinstance(trace_id, str) else new_trace_id(),
                observation_id=call_id or new_trace_id(),
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                latency_ms=round((perf_counter() - started) * 1000, 2),
                status=status,
                error_code=error_code,
                metadata={"has_agent_run": state.get("agent_run_id") is not None},
            ),
        )

    async def _finish_record(
        self,
        record: object | None,
        status: str,
        *,
        result: JSONValue | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        if self.recorder is None or record is None:
            return
        await self.recorder.update_status(
            record,
            status=status,
            result=result,
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )

    async def _mark_record_running(self, record: object | None) -> None:
        if self.recorder is None or record is None:
            return
        await self.recorder.update_status(record, status="running")
