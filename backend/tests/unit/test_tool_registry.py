"""Unit tests for Tool Registry contracts and execution behavior."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.agents.state import AgentState, JSONValue
from app.tools.registry import BaseTool, ToolContext, ToolError, ToolRegistry, ToolRegistryError


class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Return the supplied value."

    @property
    def input_schema(self) -> dict[str, JSONValue]:
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }

    async def execute(self, arguments: dict[str, JSONValue], context: ToolContext) -> JSONValue:
        return {"value": arguments["value"], "user_id": str(context.user_id)}


class FailingTool(EchoTool):
    @property
    def name(self) -> str:
        return "failing"

    async def execute(self, arguments: dict[str, JSONValue], context: ToolContext) -> JSONValue:
        raise ToolError("TOOL_REJECTED", "Tool rejected the request")


class SlowTool(EchoTool):
    @property
    def name(self) -> str:
        return "slow"

    async def execute(self, arguments: dict[str, JSONValue], context: ToolContext) -> JSONValue:
        await asyncio.sleep(0.05)
        return arguments["value"]


class DangerousTool(EchoTool):
    @property
    def name(self) -> str:
        return "send_notification"

    @property
    def requires_approval(self) -> bool:
        return True


@dataclass
class FakeRecorder:
    created: list[dict[str, object]]
    updates: list[dict[str, object]]

    def __init__(self) -> None:
        self.created = []
        self.updates = []

    async def create(self, **kwargs: object) -> object:
        self.created.append(kwargs)
        return kwargs

    async def update_status(self, record: object, **kwargs: object) -> object:
        self.updates.append({"record": record, **kwargs})
        return record


def state() -> AgentState:
    return {
        "user_id": uuid4(),
        "conversation_id": uuid4(),
        "agent_id": uuid4(),
        "agent_run_id": uuid4(),
        "knowledge_base_id": None,
        "metadata": {},
    }


def test_registry_registers_descriptors_and_rejects_duplicates() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())

    assert registry.list_descriptors()[0].name == "echo"
    assert registry.get_descriptor("echo").input_schema["type"] == "object"
    with pytest.raises(ToolRegistryError):
        registry.register(EchoTool())


@pytest.mark.asyncio
async def test_registry_validates_executes_and_records_tool_call() -> None:
    recorder = FakeRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(EchoTool())
    current_state = state()

    result = await registry.execute(
        {
            "call_id": "call-1",
            "name": "echo",
            "arguments": {"value": "safe"},
        },
        current_state,
    )

    assert result.error_code is None
    assert result.result["value"] == "safe"
    assert recorder.created[0]["agent_run_id"] == current_state["agent_run_id"]
    assert recorder.updates[-1]["status"] == "completed"
    assert recorder.updates[-1]["duration_ms"] is not None


@pytest.mark.asyncio
async def test_registry_converts_unknown_invalid_and_tool_errors() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(FailingTool())
    current_state = state()

    unknown = await registry.execute(
        {"call_id": "unknown", "name": "missing", "arguments": {}}, current_state
    )
    invalid = await registry.execute(
        {"call_id": "invalid", "name": "echo", "arguments": {"value": 3}}, current_state
    )
    failed = await registry.execute(
        {"call_id": "failed", "name": "failing", "arguments": {"value": "x"}},
        current_state,
    )

    assert unknown.error_code == "TOOL_NOT_FOUND"
    assert invalid.error_code == "TOOL_INVALID_INPUT"
    assert failed.error_code == "TOOL_REJECTED"


@pytest.mark.asyncio
async def test_registry_enforces_execution_timeout() -> None:
    registry = ToolRegistry(timeout_seconds=0.001)
    registry.register(SlowTool())

    result = await registry.execute(
        {"call_id": "slow", "name": "slow", "arguments": {"value": "x"}}, state()
    )

    assert result.error_code == "TOOL_TIMEOUT"


@pytest.mark.asyncio
async def test_registry_requires_approval_before_dangerous_tool_execution() -> None:
    registry = ToolRegistry()
    registry.register(DangerousTool())

    result = await registry.execute(
        {"call_id": "approval-call", "name": "send_notification", "arguments": {"value": "x"}},
        state(),
    )

    assert result.approval_required is True
    assert result.error_code is None
    assert registry.get_descriptor("send_notification").requires_approval is True
