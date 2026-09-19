"""Bounded asynchronous Agent runtime over a LangGraph graph."""

import asyncio
import logging
from copy import deepcopy

from app.agents.contracts import (
    AgentRuntimeConfig,
    AgentRuntimeError,
    AgentStepHandler,
    ToolExecutor,
)
from app.agents.graph import build_agent_graph
from app.agents.state import AgentState
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Execute a graph with max-step, timeout, and cancellation controls."""

    def __init__(
        self,
        step_handler: AgentStepHandler,
        tool_executor: ToolExecutor,
        config: AgentRuntimeConfig | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        self.config = config or AgentRuntimeConfig()
        self.cancel_event = cancel_event
        self.graph = build_agent_graph(
            step_handler,
            tool_executor,
            self.config,
            cancel_event,
        )

    @classmethod
    def from_settings(
        cls,
        step_handler: AgentStepHandler,
        tool_executor: ToolExecutor,
        settings: Settings | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> "AgentRuntime":
        resolved = settings or get_settings()
        return cls(
            step_handler,
            tool_executor,
            AgentRuntimeConfig(
                max_steps=resolved.agent_max_steps,
                timeout_seconds=resolved.agent_timeout_seconds,
            ),
            cancel_event,
        )

    async def run(self, initial_state: AgentState) -> AgentState:
        state = deepcopy(initial_state)
        state.setdefault("messages", [])
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])
        state.setdefault("metadata", {})
        state.setdefault("step_count", 0)
        state.setdefault("max_steps", self.config.max_steps)
        state["status"] = "running"
        if self.cancel_event is not None and self.cancel_event.is_set():
            return self._failure_state(state, "AGENT_CANCELLED", "Agent run was cancelled", "cancelled")
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                result = await self.graph.ainvoke(state)
            final_state = AgentState(**result)
            if final_state.get("status") == "running":
                final_state["status"] = "completed"
            return final_state
        except TimeoutError:
            return self._failure_state(state, "AGENT_TIMEOUT", "Agent run timed out", "failed")
        except AgentRuntimeError as exc:
            status = "cancelled" if exc.code == "AGENT_CANCELLED" else "failed"
            return self._failure_state(state, exc.code, exc.message, status)
        except Exception as exc:
            logger.exception("Agent runtime failed")
            return self._failure_state(state, "AGENT_RUNTIME_FAILED", "Agent runtime failed", "failed", exc)

    @staticmethod
    def _failure_state(
        state: AgentState,
        code: str,
        message: str,
        status: str,
        cause: BaseException | None = None,
    ) -> AgentState:
        if cause is not None:
            logger.error("Agent runtime exception", extra={"error_code": code})
        state["status"] = status  # type: ignore[typeddict-item]
        state["error_code"] = code
        state["error_message"] = message
        return state
