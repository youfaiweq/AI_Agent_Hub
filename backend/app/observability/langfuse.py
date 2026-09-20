"""Langfuse OTLP adapter with fail-open delivery semantics."""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.observability.contracts import ObservationEvent

logger = logging.getLogger(__name__)


class LangfuseAdapter:
    """Send sanitized events to Langfuse without blocking business requests."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._tasks: set[asyncio.Task[None]] = set()

    async def emit(self, event: ObservationEvent) -> None:
        if not self._configured():
            return
        task = asyncio.create_task(self._send(event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def flush(self) -> None:
        """Wait for queued telemetry in tests or graceful shutdown paths."""

        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    def _configured(self) -> bool:
        return bool(
            self.settings.langfuse_enabled
            and self.settings.langfuse_public_key.get_secret_value()
            and self.settings.langfuse_secret_key.get_secret_value()
        )

    async def _send(self, event: ObservationEvent) -> None:
        payload = self._payload(event)
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.settings.langfuse_timeout_seconds)
        try:
            response = await client.post(
                self._endpoint(),
                auth=(
                    self.settings.langfuse_public_key.get_secret_value(),
                    self.settings.langfuse_secret_key.get_secret_value(),
                ),
                headers={
                    "Content-Type": "application/json",
                    "x-langfuse-ingestion-version": "4",
                },
                json=payload,
            )
            response.raise_for_status()
        except (httpx.HTTPError, TimeoutError) as exc:
            logger.warning("Langfuse telemetry delivery failed", extra={"error_type": type(exc).__name__})
        finally:
            if owns_client:
                await client.aclose()

    def _endpoint(self) -> str:
        return f"{self.settings.langfuse_base_url.rstrip('/')}/api/public/otel/v1/traces"

    @staticmethod
    def _payload(event: ObservationEvent) -> dict[str, Any]:
        trace_id = _hex_id(event.trace_id, 32)
        span_id = _hex_id(event.observation_id, 16)
        attributes: list[dict[str, object]] = [
            _attribute("langfuse.observation.type", event.kind),
            _attribute("langfuse.observation.status", event.status),
            _attribute("agenthub.latency_ms", event.latency_ms),
        ]
        if event.model:
            attributes.append(_attribute("gen_ai.request.model", event.model))
        if event.error_code:
            attributes.append(_attribute("agenthub.error_code", event.error_code))
        for key, value in event.metadata.items():
            attributes.append(_attribute(f"agenthub.{key}", value))
        if event.usage:
            for key, value in event.usage.items():
                attributes.append(_attribute(f"gen_ai.usage.{key}", value))
        return {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "scope": {"name": "agenthub"},
                            "spans": [
                                {
                                    "traceId": trace_id,
                                    "spanId": span_id,
                                    "name": f"agenthub.{event.kind}.{event.name}",
                                    "startTimeUnixNano": str(_nanos(event.started_at)),
                                    "endTimeUnixNano": str(_nanos(event.ended_at)),
                                    "attributes": attributes,
                                }
                            ],
                        }
                    ]
                }
            ]
        }


def _hex_id(value: str, length: int) -> str:
    normalized = "".join(char for char in value if char in "0123456789abcdefABCDEF")
    return (normalized + uuid4().hex)[:length].lower()


def _nanos(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _attribute(key: str, value: str | float | bool) -> dict[str, object]:
    if isinstance(value, bool):
        typed: dict[str, object] = {"boolValue": value}
    elif isinstance(value, int):
        typed = {"intValue": str(value)}
    elif isinstance(value, float):
        typed = {"doubleValue": value}
    else:
        typed = {"stringValue": value}
    return {"key": key, "value": typed}
