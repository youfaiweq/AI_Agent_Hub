"""Application health endpoint."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Final

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.database import ping_database
from app.integrations.minio import MinioAdapter
from app.integrations.qdrant import QdrantAdapter
from app.integrations.redis import RedisAdapter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])

HEALTHY: Final[str] = "healthy"
UNHEALTHY: Final[str] = "unhealthy"


class ServiceHealth(BaseModel):
    """Health result for one infrastructure service."""

    status: str
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Aggregated health response."""

    status: str = Field(description="healthy when all dependencies respond")
    timestamp: datetime
    services: dict[str, ServiceHealth]


def _healthy(started_at: float) -> ServiceHealth:
    return ServiceHealth(
        status=HEALTHY,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )


def _failed(started_at: float, service_name: str, exc: Exception) -> ServiceHealth:
    logger.warning(
        "Infrastructure health check failed",
        extra={"service": service_name, "error_type": type(exc).__name__},
    )
    return ServiceHealth(
        status=UNHEALTHY,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        error="service unavailable",
    )


async def _check_postgres() -> ServiceHealth:
    started_at = time.perf_counter()
    try:
        await ping_database()
        return _healthy(started_at)
    except Exception as exc:  # noqa: BLE001 - health checks must report dependency failure
        return _failed(started_at, "postgresql", exc)


async def _check_redis() -> ServiceHealth:
    started_at = time.perf_counter()
    try:
        async with RedisAdapter() as adapter:
            await adapter.ping()
        return _healthy(started_at)
    except Exception as exc:  # noqa: BLE001 - health checks must report dependency failure
        return _failed(started_at, "redis", exc)


async def _check_qdrant() -> ServiceHealth:
    started_at = time.perf_counter()
    try:
        async with QdrantAdapter() as adapter:
            await adapter.readiness()
        return _healthy(started_at)
    except Exception as exc:  # noqa: BLE001 - health checks must report dependency failure
        return _failed(started_at, "qdrant", exc)


async def _check_minio() -> ServiceHealth:
    started_at = time.perf_counter()
    try:
        async with MinioAdapter() as adapter:
            await adapter.health_check()
        return _healthy(started_at)
    except Exception as exc:  # noqa: BLE001 - health checks must report dependency failure
        return _failed(started_at, "minio", exc)


async def _check_dependencies() -> dict[str, ServiceHealth]:
    results = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        _check_qdrant(),
        _check_minio(),
    )
    return dict(zip(("postgresql", "redis", "qdrant", "minio"), results, strict=True))


@router.get("/health", response_model=HealthResponse, summary="Check API and infrastructure health")
async def health_check() -> HealthResponse:
    """Return the API health and the state of configured infrastructure services."""

    services = await _check_dependencies()
    status = HEALTHY if all(item.status == HEALTHY for item in services.values()) else "degraded"
    return HealthResponse(status=status, timestamp=datetime.now(UTC), services=services)
