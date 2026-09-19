"""Redis connection adapter."""

from typing import Protocol, Self

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.integrations.errors import IntegrationError


class RedisClientProtocol(Protocol):
    """Minimal async Redis surface required by the adapter."""

    async def ping(self) -> bool: ...

    async def aclose(self) -> None: ...


class RedisAdapter:
    """Manage a Redis client with bounded connection and command timeouts."""

    service_name = "redis"

    def __init__(
        self,
        settings: Settings | None = None,
        client: RedisClientProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> RedisClientProtocol:
        if self._client is None:
            self._client = Redis.from_url(
                self._settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=self._settings.integration_timeout_seconds,
                socket_timeout=self._settings.integration_timeout_seconds,
            )
        return self._client

    async def ping(self) -> bool:
        """Verify Redis connectivity."""

        try:
            return bool(await self._get_client().ping())
        except Exception as exc:
            raise IntegrationError(self.service_name, "ping") from exc

    async def close(self) -> None:
        """Close the underlying Redis client if it was created."""

        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
