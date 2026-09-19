"""Qdrant connection adapter."""

from typing import Protocol, Self

from qdrant_client import AsyncQdrantClient

from app.core.config import Settings, get_settings
from app.integrations.errors import IntegrationError


class QdrantClientProtocol(Protocol):
    """Minimal async Qdrant surface required by the adapter."""

    async def get_collections(self) -> object: ...

    async def close(self) -> None: ...


class QdrantAdapter:
    """Manage a Qdrant client and expose a readiness probe."""

    service_name = "qdrant"

    def __init__(
        self,
        settings: Settings | None = None,
        client: QdrantClientProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> QdrantClientProtocol:
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self._settings.qdrant_url,
                timeout=self._settings.integration_timeout_seconds,
            )
        return self._client

    async def readiness(self) -> bool:
        """Verify that Qdrant accepts a collections request."""

        try:
            await self._get_client().get_collections()
            return True
        except Exception as exc:
            raise IntegrationError(self.service_name, "readiness") from exc

    async def close(self) -> None:
        """Close the underlying Qdrant client if it was created."""

        if self._client is not None:
            await self._client.close()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
