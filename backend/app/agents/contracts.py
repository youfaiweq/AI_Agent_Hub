"""Provider-neutral Agent step and tool execution contracts."""

from dataclasses import dataclass, field
from typing import Protocol

from app.agents.state import AgentMessage, AgentState, JSONValue, ToolCallState


class AgentRuntimeError(RuntimeError):
    """Normalized runtime control or execution error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AgentRuntimeConfig:
    """Hard runtime limits that prevent unbounded Agent execution."""

    max_steps: int = 10
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise AgentRuntimeError("INVALID_MAX_STEPS", "max_steps must be greater than zero")
        if self.timeout_seconds <= 0:
            raise AgentRuntimeError(
                "INVALID_TIMEOUT", "timeout_seconds must be greater than zero"
            )


@dataclass(frozen=True)
class AgentDecision:
    """One model/decision-node update to the runtime state."""

    assistant_message: AgentMessage | None = None
    tool_call: ToolCallState | None = None
    done: bool = False
    metadata: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolExecutionResult:
    """Normalized result returned by a future Tool Registry executor."""

    result: JSONValue = None
    error_code: str | None = None
    error_message: str | None = None


class AgentStepHandler(Protocol):
    """Contract for the decision/model node implemented in a later task."""

    async def decide(self, state: AgentState) -> AgentDecision: ...


class ToolExecutor(Protocol):
    """Contract for the Tool Registry executor implemented in a later task."""

    async def execute(
        self,
        tool_call: ToolCallState,
        state: AgentState,
    ) -> ToolExecutionResult: ...
