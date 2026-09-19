"""JSON decision handler for the first non-streaming Agent API."""

import json
from uuid import uuid4

from app.agents.contracts import AgentDecision, AgentRuntimeError, AgentStepHandler
from app.agents.state import AgentState
from app.rag.llms.base import LLMError, LLMMessage, LLMProvider
from app.tools.registry import ToolDescriptor


class LLMDecisionHandler(AgentStepHandler):
    """Ask the configured LLM for a strict answer-or-tool JSON decision."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: tuple[ToolDescriptor, ...],
        system_prompt: str | None = None,
        *,
        final_llm: LLMProvider | None = None,
        history_limit: int = 8,
        tool_results_limit: int = 4,
    ) -> None:
        if history_limit <= 0 or tool_results_limit <= 0:
            raise ValueError("Agent context limits must be greater than zero")
        self.router_llm = llm
        self.final_llm = final_llm or llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.history_limit = history_limit
        self.tool_results_limit = tool_results_limit

    async def decide(self, state: AgentState) -> AgentDecision:
        prompt = self._system_prompt()
        messages = [LLMMessage(role="system", content=prompt)]
        messages.extend(
            LLMMessage(role=item["role"], content=item["content"])
            for item in state.get("messages", [])[-self.history_limit :]
            if item.get("role") in {"user", "assistant"}
        )
        tool_results = state.get("tool_results", [])[-self.tool_results_limit :]
        if tool_results:
            messages.append(
                LLMMessage(
                    role="user",
                    content="Tool results from the previous step:\n"
                    + json.dumps(tool_results, ensure_ascii=False, default=str),
                )
            )
        try:
            active_llm = self.final_llm if tool_results else self.router_llm
            response = await active_llm.generate(messages)
        except LLMError as exc:
            raise AgentRuntimeError("AGENT_LLM_FAILED", exc.message) from exc
        return self._parse_decision(response.content)

    def _system_prompt(self) -> str:
        custom = self.system_prompt.strip() if self.system_prompt else "Answer helpfully and concisely."
        tool_catalog = json.dumps(
            [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in self.tools
            ],
            ensure_ascii=False,
        )
        return (
            f"{custom}\n"
            "You are the AgentHub runtime decision layer. Return ONLY valid JSON. "
            "Use exactly one of these shapes: "
            '{"action":"answer","content":"..."} or '
            '{"action":"tool","name":"tool_name","arguments":{...}}. '
            "Use a tool when it materially helps answer the user. "
            f"Available tools: {tool_catalog}"
        )

    def _parse_decision(self, content: str) -> AgentDecision:
        try:
            parsed = json.loads(self._strip_code_fence(content))
        except json.JSONDecodeError as exc:
            raise AgentRuntimeError("AGENT_INVALID_DECISION", "Agent returned invalid JSON") from exc
        if not isinstance(parsed, dict) or parsed.get("action") not in {"answer", "tool"}:
            raise AgentRuntimeError("AGENT_INVALID_DECISION", "Agent returned an unknown action")
        if parsed["action"] == "answer":
            answer = parsed.get("content")
            if not isinstance(answer, str) or not answer.strip():
                raise AgentRuntimeError("AGENT_INVALID_DECISION", "Agent answer content is empty")
            return AgentDecision(
                assistant_message={"role": "assistant", "content": answer.strip()},
                done=True,
            )
        name = parsed.get("name")
        arguments = parsed.get("arguments", {})
        if not isinstance(name, str) or not name or not isinstance(arguments, dict):
            raise AgentRuntimeError("AGENT_INVALID_DECISION", "Agent tool decision is malformed")
        return AgentDecision(
            tool_call={
                "call_id": str(uuid4()),
                "name": name,
                "arguments": arguments,
                "status": "pending",
            }
        )

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped[3:-3].strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        return stripped
