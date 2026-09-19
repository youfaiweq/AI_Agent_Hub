"""Qdrant vector store adapter."""

from dataclasses import dataclass
from typing import Protocol, Self
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.core.config import Settings, get_settings
from app.integrations.errors import IntegrationError
from app.rag.contracts import Chunk


class QdrantVectorClientProtocol(Protocol):
    async def get_collections(self) -> object: ...

    async def collection_exists(self, collection_name: str) -> bool: ...

    async def create_collection(self, collection_name: str, vectors_config: VectorParams) -> bool: ...

    async def upsert(self, collection_name: str, points: list[PointStruct], wait: bool = True) -> object: ...

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        with_payload: bool = True,
    ) -> list[ScoredPoint]: ...

    async def delete(
        self,
        collection_name: str,
        points_selector: FilterSelector,
        wait: bool = True,
    ) -> object: ...

    async def close(self) -> None: ...


@dataclass(frozen=True)
class VectorSearchResult:
    """Search result with score and original chunk payload."""

    point_id: str
    score: float
    payload: dict[str, object]


class QdrantVectorStore:
    """Manage one Qdrant collection per knowledge base."""

    service_name = "qdrant"

    def __init__(
        self,
        settings: Settings | None = None,
        client: QdrantVectorClientProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> QdrantVectorClientProtocol:
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self._settings.qdrant_url,
                timeout=self._settings.integration_timeout_seconds,
            )
        return self._client

    def collection_name(self, knowledge_base_id: UUID) -> str:
        return f"{self._settings.qdrant_collection_prefix}_{knowledge_base_id.hex}"

    async def health_check(self) -> bool:
        try:
            await self._get_client().get_collections()
            return True
        except Exception as exc:
            raise IntegrationError(self.service_name, "vector_health_check") from exc

    async def ensure_collection(self, knowledge_base_id: UUID) -> str:
        collection_name = self.collection_name(knowledge_base_id)
        try:
            client = self._get_client()
            if not await client.collection_exists(collection_name):
                await client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self._settings.embedding_dimension,
                        distance=Distance.COSINE,
                    ),
                )
            return collection_name
        except Exception as exc:
            raise IntegrationError(self.service_name, "ensure_collection") from exc

    async def upsert_chunks(
        self,
        knowledge_base_id: UUID,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if any(len(vector) != self._settings.embedding_dimension for vector in vectors):
            raise ValueError("vector dimension does not match the configured embedding dimension")
        if not chunks:
            return
        collection_name = await self.ensure_collection(knowledge_base_id)
        points = [
            PointStruct(
                id=str(chunk.chunk_id),
                vector=vector,
                payload={
                    "knowledge_base_id": str(knowledge_base_id),
                    "document_id": str(chunk.metadata.document_id),
                    "chunk_id": str(chunk.chunk_id),
                    "filename": chunk.metadata.filename,
                    "page_number": chunk.metadata.page_number,
                    "start_char": chunk.metadata.start_char,
                    "end_char": chunk.metadata.end_char,
                    "text": chunk.text,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            await self._get_client().upsert(collection_name, points, wait=True)
        except Exception as exc:
            raise IntegrationError(self.service_name, "upsert") from exc

    async def search(
        self,
        knowledge_base_id: UUID,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        if len(query_vector) != self._settings.embedding_dimension:
            raise ValueError("query vector dimension does not match the configured embedding dimension")
        collection_name = await self.ensure_collection(knowledge_base_id)
        try:
            points = await self._get_client().search(
                collection_name,
                query_vector=query_vector,
                limit=limit,
                with_payload=True,
            )
            return [self._to_result(point) for point in points]
        except Exception as exc:
            raise IntegrationError(self.service_name, "search") from exc

    async def delete_document(self, knowledge_base_id: UUID, document_id: UUID) -> None:
        collection_name = self.collection_name(knowledge_base_id)
        try:
            if not await self._get_client().collection_exists(collection_name):
                return
            selector = FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        )
                    ]
                )
            )
            await self._get_client().delete(collection_name, selector, wait=True)
        except Exception as exc:
            raise IntegrationError(self.service_name, "delete_document") from exc

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @staticmethod
    def _to_result(point: ScoredPoint) -> VectorSearchResult:
        return VectorSearchResult(
            point_id=str(point.id),
            score=float(point.score),
            payload=dict(point.payload or {}),
        )
