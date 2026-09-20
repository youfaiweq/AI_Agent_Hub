"""Tests for non-streaming LLM Agent decision parsing."""

import pytest

from app.agents.llm_handler import LLMDecisionHandler
from app.agents.state import AgentState
from app.rag.llms.base import LLMMessage, LLMResponse
from app.tools.registry import ToolDescriptor


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[list[LLMMessage]] = []

    async def generate(self, messages):
        self.messages.append(list(messages))
        return LLMResponse(content=self.content, model="test")


class SequencedLLM(FakeLLM):
    def __init__(self, contents: list[str]) -> None:
        super().__init__(contents[0])
        self.contents = contents

    async def generate(self, messages):
        self.messages.append(list(messages))
        return LLMResponse(content=self.contents.pop(0), model="test")


def state() -> AgentState:
    return {"messages": [{"role": "user", "content": "What is 2+2?"}], "tool_results": []}


@pytest.mark.asyncio
async def test_llm_decision_handler_parses_answer() -> None:
    handler = LLMDecisionHandler(FakeLLM('{"action":"answer","content":"4"}'), ())

    decision = await handler.decide(state())

    assert decision.done is True
    assert decision.assistant_message == {"role": "assistant", "content": "4"}


@pytest.mark.asyncio
async def test_llm_decision_handler_parses_tool_call_and_catalog() -> None:
    llm = FakeLLM('{"action":"tool","name":"calculator","arguments":{"expression":"2+2"}}')
    handler = LLMDecisionHandler(
        llm,
        (
            ToolDescriptor(
                name="calculator",
                description="Calculate",
                input_schema={"type": "object"},
            ),
        ),
    )

    decision = await handler.decide(state())

    assert decision.tool_call is not None
    assert decision.tool_call["name"] == "calculator"
    assert decision.tool_call["arguments"] == {"expression": "2+2"}
    assert "calculator" in llm.messages[0][0].content


@pytest.mark.asyncio
async def test_llm_decision_handler_switches_to_final_model_after_tool_results() -> None:
    router = FakeLLM('{"action":"tool","name":"calculator","arguments":{"expression":"2+2"}}')
    final = FakeLLM('{"action":"answer","content":"4"}')
    handler = LLMDecisionHandler(
        router,
        (),
        final_llm=final,
        history_limit=2,
        tool_results_limit=1,
    )

    tool_decision = await handler.decide(state())
    final_state = {
        "messages": [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "tool"},
            {"role": "user", "content": "new"},
        ],
        "tool_results": [{"result": 4}, {"result": 5}],
    }
    answer_decision = await handler.decide(final_state)

    assert tool_decision.tool_call is not None
    assert answer_decision.assistant_message == {"role": "assistant", "content": "4"}
    assert len(final.messages) == 1
    assert "5" in final.messages[0][-1].content
    assert "old" not in final.messages[0][-1].content


@pytest.mark.asyncio
async def test_llm_decision_handler_keeps_current_message_outside_history_budget() -> None:
    llm = FakeLLM('{"action":"answer","content":"ok"}')
    handler = LLMDecisionHandler(llm, (), history_limit=2, context_token_budget=1)
    current = "This current request must remain complete."

    await handler.decide({"messages": [{"role": "user", "content": current}], "tool_results": []})

    assert llm.messages[0][-1].content == current
