"""Unit tests for the provider-neutral observability layer."""

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.observability import (
    InMemoryObservabilityAdapter,
    LangfuseAdapter,
    ObservationEvent,
    ObservedLLMProvider,
    observe,
)
from app.rag.llms.base import LLMError, LLMMessage, LLMProvider, LLMResponse


class FakeLLM(LLMProvider):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        if self.fail:
            raise LLMError("LLM_FAILED", "provider failed")
        return LLMResponse(content="answer", model="test-model", usage={"prompt_tokens": 4, "completion_tokens": 2})


@pytest.mark.asyncio
async def test_observed_llm_emits_model_usage_and_error_events() -> None:
    adapter = InMemoryObservabilityAdapter()
    provider = ObservedLLMProvider(FakeLLM(), adapter, trace_id="trace-1")

    response = await provider.generate([LLMMessage(role="user", content="question")])

    assert response.model == "test-model"
    assert adapter.events[0].kind == "generation"
    assert adapter.events[0].model == "test-model"
    assert adapter.events[0].usage == {"prompt_tokens": 4, "completion_tokens": 2}

    with pytest.raises(LLMError):
        await ObservedLLMProvider(FakeLLM(fail=True), adapter, trace_id="trace-2").generate([])
    assert adapter.events[-1].status == "failed"
    assert adapter.events[-1].error_code == "LLM_FAILED"


@pytest.mark.asyncio
async def test_observe_preserves_errors_and_emits_failed_event() -> None:
    adapter = InMemoryObservabilityAdapter()

    with pytest.raises(ValueError):
        async with observe(adapter, kind="agent_run", name="run", trace_id="trace-1"):
            raise ValueError("boom")

    assert adapter.events[0].status == "failed"
    assert adapter.events[0].error_code == "ValueError"


@pytest.mark.asyncio
async def test_langfuse_adapter_sends_otlp_payload_without_business_content() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202)

    settings = Settings(
        langfuse_enabled=True,
        langfuse_public_key=SecretStr("public-test"),
        langfuse_secret_key=SecretStr("secret-test"),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LangfuseAdapter(settings, client)
        await adapter.emit(
            ObservationEvent(
                kind="generation",
                name="test",
                trace_id="trace-1",
                observation_id="span-1",
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                latency_ms=1.5,
                model="test-model",
                usage={"prompt_tokens": 2},
                metadata={"message_count": 1},
            )
        )
        await adapter.flush()

    assert requests[0].url.path == "/api/public/otel/v1/traces"
    assert requests[0].headers["x-langfuse-ingestion-version"] == "4"
    body = requests[0].content.decode()
    assert "test-model" in body
    assert "question" not in body
    assert "secret-test" not in body
