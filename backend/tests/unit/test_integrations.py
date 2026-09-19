"""Unit tests for infrastructure adapters using injected Test Adapters."""

import pytest

from app.integrations.errors import IntegrationError
from app.integrations.minio import MinioAdapter
from app.integrations.qdrant import QdrantAdapter
from app.integrations.redis import RedisAdapter


class HealthyRedisClient:
    def __init__(self) -> None:
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True


class HealthyQdrantClient:
    def __init__(self) -> None:
        self.closed = False

    async def get_collections(self) -> object:
        return {"collections": []}

    async def close(self) -> None:
        self.closed = True


class HealthyMinioClient:
    def list_buckets(self) -> list[object]:
        return []

    def bucket_exists(self, bucket_name: str) -> bool:
        return bucket_name == "agenthub"


class BrokenRedisClient:
    async def ping(self) -> bool:
        raise OSError("test connection failure")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_redis_adapter_uses_injected_client_and_closes_it() -> None:
    client = HealthyRedisClient()

    async with RedisAdapter(client=client) as adapter:
        assert await adapter.ping() is True

    assert client.closed is True


@pytest.mark.asyncio
async def test_qdrant_adapter_checks_readiness_and_closes_it() -> None:
    client = HealthyQdrantClient()

    async with QdrantAdapter(client=client) as adapter:
        assert await adapter.readiness() is True

    assert client.closed is True


@pytest.mark.asyncio
async def test_minio_adapter_checks_api_and_bucket() -> None:
    async with MinioAdapter(client=HealthyMinioClient()) as adapter:
        assert await adapter.health_check() is True
        assert await adapter.bucket_exists() is True


@pytest.mark.asyncio
async def test_adapter_normalizes_client_errors() -> None:
    with pytest.raises(IntegrationError) as error_info:
        await RedisAdapter(client=BrokenRedisClient()).ping()

    assert error_info.value.service == "redis"
    assert error_info.value.operation == "ping"
