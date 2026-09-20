"""Unit tests for the bounded LangGraph Agent runtime contracts."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.agents.contracts import (
    AgentDecision,
    AgentRuntimeConfig,
    AgentRuntimeError,
    ToolExecutionResult,
)
from app.agents.runtime import AgentRuntime


@dataclass
class ScriptedHandler:
    decisions: list[AgentDecision]

    async def decide(self, state):
        return self.decisions.pop(0)


class RecordingToolExecutor:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, tool_call, state):
        self.calls.append(tool_call)
        return ToolExecutionResult(result={"value": "tool result"})


class ApprovalToolExecutor(RecordingToolExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.approved = False

    async def execute(self, tool_call, state):
        self.calls.append(tool_call)
        if not self.approved:
            return ToolExecutionResult(
                approval_required=True,
                approval_message="Approval required",
            )
        return ToolExecutionResult(result={"value": "approved result"})


def initial_state() -> dict:
    return {
        "user_id": uuid4(),
        "conversation_id": uuid4(),
        "agent_id": uuid4(),
        "knowledge_base_id": uuid4(),
        "messages": [{"role": "user", "content": "Question"}],
    }


@pytest.mark.asyncio
async def test_agent_runtime_completes_without_tools() -> None:
    handler = ScriptedHandler(
        [AgentDecision(assistant_message={"role": "assistant", "content": "Answer"}, done=True)]
    )
    runtime = AgentRuntime(handler, RecordingToolExecutor())

    result = await runtime.run(initial_state())

    assert result["status"] == "completed"
    assert result["step_count"] == 1
    assert result["messages"][-1]["content"] == "Answer"


@pytest.mark.asyncio
async def test_agent_runtime_executes_tool_then_returns_to_agent() -> None:
    tool_executor = RecordingToolExecutor()
    handler = ScriptedHandler(
        [
            AgentDecision(
                tool_call={
                    "call_id": "call-1",
                    "name": "calculator",
                    "arguments": {"expression": "1 + 1"},
                    "status": "pending",
                }
            ),
            AgentDecision(assistant_message={"role": "assistant", "content": "2"}, done=True),
        ]
    )
    runtime = AgentRuntime(handler, tool_executor)

    result = await runtime.run(initial_state())

    assert result["status"] == "completed"
    assert result["step_count"] == 2
    assert result["tool_results"] == [{"value": "tool result"}]
    assert result["tool_calls"][0]["status"] == "completed"
    assert tool_executor.calls[0]["name"] == "calculator"


@pytest.mark.asyncio
async def test_agent_runtime_enforces_max_steps() -> None:
    handler = ScriptedHandler([AgentDecision() for _ in range(3)])
    runtime = AgentRuntime(
        handler,
        RecordingToolExecutor(),
        AgentRuntimeConfig(max_steps=2, timeout_seconds=1),
    )

    result = await runtime.run(initial_state())

    assert result["status"] == "failed"
    assert result["error_code"] == "MAX_STEPS_EXCEEDED"
    assert result["step_count"] == 2


@pytest.mark.asyncio
async def test_agent_runtime_normalizes_timeout_and_cancellation() -> None:
    class SlowHandler:
        async def decide(self, state):
            await asyncio.sleep(0.05)
            return AgentDecision(done=True)

    timed_out = await AgentRuntime(
        SlowHandler(),
        RecordingToolExecutor(),
        AgentRuntimeConfig(max_steps=2, timeout_seconds=0.001),
    ).run(initial_state())
    assert timed_out["status"] == "failed"
    assert timed_out["error_code"] == "AGENT_TIMEOUT"

    cancel_event = asyncio.Event()
    cancel_event.set()
    cancelled = await AgentRuntime(
        ScriptedHandler([AgentDecision(done=True)]),
        RecordingToolExecutor(),
        cancel_event=cancel_event,
    ).run(initial_state())
    assert cancelled["status"] == "cancelled"
    assert cancelled["error_code"] == "AGENT_CANCELLED"


def test_agent_runtime_config_rejects_unbounded_limits() -> None:
    with pytest.raises(AgentRuntimeError):
        AgentRuntimeConfig(max_steps=0)
    with pytest.raises(AgentRuntimeError):
        AgentRuntimeConfig(timeout_seconds=0)


@pytest.mark.asyncio
async def test_agent_runtime_interrupts_and_resumes_approved_tool_call() -> None:
    executor = ApprovalToolExecutor()
    runtime = AgentRuntime(
        ScriptedHandler(
            [
                AgentDecision(
                    tool_call={
                        "call_id": "approval-call",
                        "name": "send_notification",
                        "arguments": {"message": "hello"},
                        "status": "pending",
                    }
                ),
                AgentDecision(assistant_message={"role": "assistant", "content": "sent"}, done=True),
            ]
        ),
        executor,
    )

    waiting = await runtime.run(initial_state())

    assert waiting["status"] == "waiting_approval"
    assert waiting["approval_request"]["tool_name"] == "send_notification"
    assert len(executor.calls) == 1

    executor.approved = True
    waiting["approved_tool_call_id"] = "approval-call"
    waiting["resume_approval"] = True
    resumed = await runtime.run(waiting)

    assert resumed["status"] == "completed"
    assert resumed["messages"][-1]["content"] == "sent"
    assert len(executor.calls) == 2
