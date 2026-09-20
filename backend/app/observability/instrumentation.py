"""Small instrumentation adapters for provider and domain boundaries."""

from collections.abc import Sequence

from app.observability.contracts import (
    ObservabilityAdapter,
    ObservationEvent,
    new_trace_id,
    safe_emit,
)
from app.rag.llms.base import LLMError, LLMMessage, LLMProvider, LLMResponse


class ObservedLLMProvider(LLMProvider):
    """Decorate an LLM provider with latency, model, usage, and error events."""

    def __init__(
        self,
        provider: LLMProvider,
        adapter: ObservabilityAdapter,
        *,
        trace_id: str | None = None,
        name: str = "llm.generate",
    ) -> None:
        self.provider = provider
        self.adapter = adapter
        self.trace_id = trace_id or new_trace_id()
        self.name = name

    async def generate(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        import time
        from datetime import UTC, datetime
        from uuid import uuid4

        started = time.perf_counter()
        started_at = datetime.now(UTC)
        model = getattr(getattr(self.provider, "settings", None), "llm_model", None)
        try:
            response = await self.provider.generate(messages)
        except LLMError as exc:
            await safe_emit(
                self.adapter,
                ObservationEvent(
                    kind="generation",
                    name=self.name,
                    trace_id=self.trace_id,
                    observation_id=uuid4().hex,
                    started_at=started_at,
                    ended_at=datetime.now(UTC),
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    status="failed",
                    model=model if isinstance(model, str) else None,
                    error_code=exc.code,
                    metadata={"message_count": len(messages)},
                ),
            )
            raise
        await safe_emit(
            self.adapter,
            ObservationEvent(
                kind="generation",
                name=self.name,
                trace_id=self.trace_id,
                observation_id=uuid4().hex,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                model=response.model,
                usage=response.usage,
                metadata={"message_count": len(messages)},
            ),
        )
        return response
