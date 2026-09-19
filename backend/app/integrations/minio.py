"""MinIO object-storage connection adapter."""

import asyncio
from io import BytesIO
from typing import Protocol, Self
from urllib.parse import urlparse

from minio import Minio

from app.core.config import Settings, get_settings
from app.integrations.errors import IntegrationError


class MinioClientProtocol(Protocol):
    """Minimal synchronous MinIO surface used behind async wrappers."""

    def list_buckets(self) -> list[object]: ...

    def bucket_exists(self, bucket_name: str) -> bool: ...

    def make_bucket(self, bucket_name: str) -> None: ...

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
    ) -> object: ...

    def remove_object(self, bucket_name: str, object_name: str) -> None: ...


def _parse_endpoint(settings: Settings) -> tuple[str, bool]:
    """Convert the configured URL into the MinIO SDK endpoint format."""

    parsed = urlparse(settings.minio_endpoint)
    endpoint = parsed.netloc or parsed.path
    secure = settings.minio_secure or parsed.scheme == "https"
    return endpoint, secure


class MinioAdapter:
    """Manage MinIO's synchronous SDK without blocking the event loop."""

    service_name = "minio"

    def __init__(
        self,
        settings: Settings | None = None,
        client: MinioClientProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> MinioClientProtocol:
        if self._client is None:
            endpoint, secure = _parse_endpoint(self._settings)
            self._client = Minio(
                endpoint,
                access_key=self._settings.minio_access_key,
                secret_key=self._settings.minio_secret_key,
                secure=secure,
            )
        return self._client

    async def health_check(self) -> bool:
        """Verify MinIO API access by listing buckets with a timeout."""

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._get_client().list_buckets),
                timeout=self._settings.integration_timeout_seconds,
            )
            return True
        except Exception as exc:
            raise IntegrationError(self.service_name, "health_check") from exc

    async def bucket_exists(self, bucket_name: str | None = None) -> bool:
        """Check whether a configured or explicitly named bucket exists."""

        name = bucket_name or self._settings.minio_bucket
        try:
            return bool(
                await asyncio.wait_for(
                    asyncio.to_thread(self._get_client().bucket_exists, name),
                    timeout=self._settings.integration_timeout_seconds,
                )
            )
        except Exception as exc:
            raise IntegrationError(self.service_name, "bucket_exists") from exc

    async def ensure_bucket(self, bucket_name: str | None = None) -> None:
        """Create the configured bucket when it does not exist."""

        name = bucket_name or self._settings.minio_bucket
        try:
            if not await self.bucket_exists(name):
                await asyncio.wait_for(
                    asyncio.to_thread(self._get_client().make_bucket, name),
                    timeout=self._settings.integration_timeout_seconds,
                )
        except Exception as exc:
            raise IntegrationError(self.service_name, "ensure_bucket") from exc

    async def put_object(
        self,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
        bucket_name: str | None = None,
    ) -> None:
        """Upload one object to the configured bucket."""

        name = bucket_name or self._settings.minio_bucket
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._get_client().put_object,
                    name,
                    object_name,
                    data,
                    length,
                    content_type=content_type,
                ),
                timeout=self._settings.integration_timeout_seconds,
            )
        except Exception as exc:
            raise IntegrationError(self.service_name, "put_object") from exc

    async def remove_object(self, object_name: str, bucket_name: str | None = None) -> None:
        """Delete one object from the configured bucket."""

        name = bucket_name or self._settings.minio_bucket
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._get_client().remove_object, name, object_name),
                timeout=self._settings.integration_timeout_seconds,
            )
        except Exception as exc:
            raise IntegrationError(self.service_name, "remove_object") from exc

    async def close(self) -> None:
        """Release adapter-owned resources; MinIO's SDK has no close call."""

        self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
