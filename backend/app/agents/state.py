"""Typed state contract shared by Agent runtime graph nodes."""

from typing import Literal, TypedDict
from uuid import UUID

AgentStatus = Literal[
    "pending",
    "running",
    "waiting_approval",
    "completed",
    "failed",
    "cancelled",
]
ToolCallStateStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
JSONValue = (
    str
    | int
    | float
    | bool
    | None
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)


class AgentMessage(TypedDict):
    """Serializable message state without binding runtime to an LLM SDK."""

    role: str
    content: str


class ToolCallState(TypedDict, total=False):
    """Serializable pending/completed tool-call state."""

    call_id: str
    name: str
    arguments: dict[str, JSONValue]
    status: ToolCallStateStatus
    result: JSONValue
    error: str


class AgentState(TypedDict, total=False):
    """Minimum state carried through the Agent graph."""

    messages: list[AgentMessage]
    user_id: UUID
    conversation_id: UUID | None
    agent_id: UUID
    agent_run_id: UUID | None
    knowledge_base_id: UUID | None
    tool_calls: list[ToolCallState]
    tool_results: list[JSONValue]
    metadata: dict[str, JSONValue]
    status: AgentStatus
    step_count: int
    max_steps: int
    error_code: str | None
    error_message: str | None
    pending_tool_call: ToolCallState | None
