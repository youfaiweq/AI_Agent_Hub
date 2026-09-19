"""Integration tests for the running infrastructure adapters."""

import pytest

from app.integrations.minio import MinioAdapter
from app.integrations.qdrant import QdrantAdapter
from app.integrations.redis import RedisAdapter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_infrastructure_adapters_reach_running_services() -> None:
    async with RedisAdapter() as redis_adapter:
        assert await redis_adapter.ping() is True

    async with QdrantAdapter() as qdrant_adapter:
        assert await qdrant_adapter.readiness() is True

    async with MinioAdapter() as minio_adapter:
        assert await minio_adapter.health_check() is True
