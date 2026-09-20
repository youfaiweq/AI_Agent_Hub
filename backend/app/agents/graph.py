"""LangGraph graph skeleton for bounded Agent execution."""

import asyncio

from langgraph.graph import END, START, StateGraph

from app.agents.contracts import (
    AgentDecision,
    AgentRuntimeConfig,
    AgentRuntimeError,
    AgentStepHandler,
    ToolExecutor,
)
from app.agents.state import AgentState, ToolCallState


def build_agent_graph(
    step_handler: AgentStepHandler,
    tool_executor: ToolExecutor,
    config: AgentRuntimeConfig,
    cancel_event: asyncio.Event | None = None,
):
    """Build START → agent → tool/END graph with bounded execution edges."""

    async def agent_node(state: AgentState) -> dict[str, object]:
        _check_cancelled(cancel_event)
        current_steps = state.get("step_count", 0)
        if current_steps >= config.max_steps:
            return _failed_update("MAX_STEPS_EXCEEDED", "Agent maximum step count exceeded")
        decision = await step_handler.decide(state)
        if not isinstance(decision, AgentDecision):
            raise AgentRuntimeError(
                "INVALID_AGENT_DECISION", "Agent step handler returned an invalid decision"
            )
        messages = list(state.get("messages", []))
        if decision.assistant_message is not None:
            messages.append(decision.assistant_message)
        tool_calls = list(state.get("tool_calls", []))
        pending_tool_call = decision.tool_call
        if pending_tool_call is not None:
            _validate_tool_call(pending_tool_call)
            tool_calls.append(pending_tool_call)
        metadata = dict(state.get("metadata", {}))
        metadata.update(decision.metadata)
        return {
            "messages": messages,
            "tool_calls": tool_calls,
            "metadata": metadata,
            "pending_tool_call": pending_tool_call,
            "step_count": current_steps + 1,
            "status": "completed" if decision.done else "running",
        }

    async def tool_node(state: AgentState) -> dict[str, object]:
        _check_cancelled(cancel_event)
        tool_call = state.get("pending_tool_call")
        if tool_call is None:
            raise AgentRuntimeError("TOOL_CALL_MISSING", "Agent tool node has no pending tool call")
        result = await tool_executor.execute(tool_call, state)
        if result.approval_required:
            updated_calls = [dict(item) for item in state.get("tool_calls", [])]
            for item in reversed(updated_calls):
                if item.get("call_id") == tool_call.get("call_id"):
                    item["status"] = "waiting_approval"
                    break
            return {
                "tool_calls": updated_calls,
                "pending_tool_call": tool_call,
                "approval_request": {
                    "tool_call_id": tool_call.get("call_id"),
                    "tool_name": tool_call.get("name"),
                    "arguments": tool_call.get("arguments", {}),
                    "message": result.approval_message or "Tool approval is required",
                    "status": "pending",
                },
                "resume_approval": False,
                "status": "waiting_approval",
            }
        tool_results = list(state.get("tool_results", []))
        tool_results.append(result.result)
        updated_calls = [dict(item) for item in state.get("tool_calls", [])]
        for item in reversed(updated_calls):
            if item.get("call_id") == tool_call.get("call_id"):
                item["status"] = "failed" if result.error_code else "completed"
                item["result"] = result.result
                if result.error_message:
                    item["error"] = result.error_message
                break
        if result.error_code:
            return {
                "tool_calls": updated_calls,
                "tool_results": tool_results,
                "pending_tool_call": None,
                "approval_request": None,
                "approved_tool_call_id": None,
                "resume_approval": False,
                **_failed_update(result.error_code, result.error_message or "Tool execution failed"),
            }
        return {
            "tool_calls": updated_calls,
            "tool_results": tool_results,
            "pending_tool_call": None,
            "approval_request": None,
            "approved_tool_call_id": None,
            "resume_approval": False,
            "status": "running",
        }

    def route_after_agent(state: AgentState) -> str:
        if state.get("status") != "running":
            return END
        if state.get("pending_tool_call") is not None:
            return "tool"
        return "agent"

    def route_after_tool(state: AgentState) -> str:
        return END if state.get("status") != "running" else "agent"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tool", tool_node)
    workflow.add_conditional_edges(START, route_after_start, {"agent": "agent", "tool": "tool"})
    workflow.add_conditional_edges(
        "agent", route_after_agent, {"agent": "agent", "tool": "tool", END: END}
    )
    workflow.add_conditional_edges("tool", route_after_tool, {"agent": "agent", END: END})
    return workflow.compile()


def route_after_start(state: AgentState) -> str:
    """Resume an approved pending tool call instead of asking the model again."""

    if state.get("resume_approval") and state.get("pending_tool_call") is not None:
        return "tool"
    return "agent"


def _check_cancelled(cancel_event: asyncio.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise AgentRuntimeError("AGENT_CANCELLED", "Agent run was cancelled")


def _validate_tool_call(tool_call: ToolCallState) -> None:
    if not tool_call.get("call_id") or not tool_call.get("name"):
        raise AgentRuntimeError("INVALID_TOOL_CALL", "Tool call requires call_id and name")


def _failed_update(code: str, message: str) -> dict[str, object]:
    return {"status": "failed", "error_code": code, "error_message": message}
