"""Provider-neutral observability contracts and safe test adapters."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class ObservationEvent:
    """A sanitized lifecycle event suitable for an external observability sink."""

    kind: str
    name: str
    trace_id: str
    observation_id: str
    started_at: datetime
    ended_at: datetime
    latency_ms: float
    status: str = "completed"
    model: str | None = None
    usage: dict[str, int] | None = None
    error_code: str | None = None
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


class ObservabilityAdapter(Protocol):
    """Non-blocking sink for sanitized observability events."""

    async def emit(self, event: ObservationEvent) -> None: ...


class NoopObservabilityAdapter:
    """Default adapter when Langfuse is disabled or not configured."""

    async def emit(self, event: ObservationEvent) -> None:
        return None


class InMemoryObservabilityAdapter:
    """Deterministic adapter used by unit tests and local diagnostics."""

    def __init__(self) -> None:
        self.events: list[ObservationEvent] = []

    async def emit(self, event: ObservationEvent) -> None:
        self.events.append(event)


def new_trace_id() -> str:
    """Create a trace id without exposing user or request content."""

    return uuid4().hex


@asynccontextmanager
async def observe(
    adapter: ObservabilityAdapter,
    *,
    kind: str,
    name: str,
    trace_id: str,
    model: str | None = None,
    metadata: dict[str, str | int | float | bool] | None = None,
) -> AsyncIterator[None]:
    """Emit one completed or failed observation while preserving the exception."""

    started_clock = perf_counter()
    started_at = datetime.now(UTC)
    status = "completed"
    error_code: str | None = None
    try:
        yield
    except Exception as exc:
        status = "failed"
        error_code = getattr(exc, "code", type(exc).__name__)
        raise
    finally:
        await adapter.emit(
            ObservationEvent(
                kind=kind,
                name=name,
                trace_id=trace_id,
                observation_id=uuid4().hex,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                latency_ms=round((perf_counter() - started_clock) * 1000, 2),
                status=status,
                model=model,
                error_code=error_code,
                metadata=metadata or {},
            )
        )


async def safe_emit(adapter: ObservabilityAdapter, event: ObservationEvent) -> None:
    """Emit without allowing telemetry failures to affect application work."""

    try:
        await adapter.emit(event)
    except Exception:  # noqa: BLE001 - telemetry must fail open
        return
