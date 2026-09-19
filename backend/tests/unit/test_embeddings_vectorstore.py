"""Contract tests for embedding and vector-store adapters."""

from uuid import uuid4

import pytest
from qdrant_client.http.models import ScoredPoint

from app.core.config import Settings
from app.rag.contracts import Chunk, ChunkMetadata
from app.rag.embeddings.base import EmbeddingError
from app.rag.embeddings.hash import HashEmbeddingProvider
from app.rag.vectorstores.qdrant import QdrantVectorStore


class FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, list[object]] = {}
        self.closed = False

    async def get_collections(self) -> object:
        return {"collections": list(self.collections)}

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    async def create_collection(self, collection_name: str, vectors_config: object) -> bool:
        self.collections.add(collection_name)
        self.points.setdefault(collection_name, [])
        return True

    async def upsert(self, collection_name: str, points: list[object], wait: bool = True) -> object:
        self.points[collection_name] = points
        return object()

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        with_payload: bool = True,
    ) -> list[ScoredPoint]:
        return [
            ScoredPoint(
                id=point.id,
                version=1,
                score=0.9,
                payload=point.payload,
            )
            for point in self.points.get(collection_name, [])[:limit]
        ]

    async def delete(self, collection_name: str, points_selector: object, wait: bool = True) -> object:
        self.points[collection_name] = []
        return object()

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_hash_embedding_provider_is_deterministic_and_dimensioned() -> None:
    provider = HashEmbeddingProvider(dimension=8)

    vectors = await provider.embed(["AgentHub knowledge", "AgentHub knowledge"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 8
    assert vectors[0] == vectors[1]
    assert pytest.approx(sum(value * value for value in vectors[0]), abs=1e-6) == 1.0

    with pytest.raises(EmbeddingError):
        await provider.embed([""])


@pytest.mark.asyncio
async def test_qdrant_vector_store_contract_upsert_search_delete() -> None:
    client = FakeQdrantClient()
    settings = Settings(embedding_dimension=8)
    store = QdrantVectorStore(settings=settings, client=client)
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk = Chunk(
        text="AgentHub",
        metadata=ChunkMetadata(
            document_id=document_id,
            filename="guide.txt",
            page_number=1,
            start_char=0,
            end_char=8,
        ),
    )
    vector = [1.0] + [0.0] * 7

    await store.upsert_chunks(knowledge_base_id, [chunk], [vector])
    results = await store.search(knowledge_base_id, vector, limit=1)

    assert store.collection_name(knowledge_base_id).startswith("agenthub_kb_")
    assert results[0].point_id == str(chunk.chunk_id)
    assert results[0].payload["document_id"] == str(document_id)

    await store.delete_document(knowledge_base_id, document_id)
    assert client.points[store.collection_name(knowledge_base_id)] == []
    await store.close()
    assert client.closed is True
