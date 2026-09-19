"""Integration tests for the running infrastructure adapters."""

from uuid import uuid4

import pytest

from app.integrations.minio import MinioAdapter
from app.integrations.qdrant import QdrantAdapter
from app.integrations.redis import RedisAdapter
from app.rag.context.builder import ContextBuilder
from app.rag.contracts import Chunk, ChunkMetadata
from app.rag.embeddings.hash import HashEmbeddingProvider
from app.rag.retrievers.dense import DenseRetriever
from app.rag.vectorstores.qdrant import QdrantVectorStore


@pytest.mark.integration
@pytest.mark.asyncio
async def test_infrastructure_adapters_reach_running_services() -> None:
    async with RedisAdapter() as redis_adapter:
        assert await redis_adapter.ping() is True

    async with QdrantAdapter() as qdrant_adapter:
        assert await qdrant_adapter.readiness() is True

    async with MinioAdapter() as minio_adapter:
        assert await minio_adapter.health_check() is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_qdrant_vector_store_round_trip() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk = Chunk(
        text="Qdrant integration document",
        metadata=ChunkMetadata(
            document_id=document_id,
            filename="integration.txt",
            page_number=1,
            start_char=0,
            end_char=29,
        ),
    )
    embedder = HashEmbeddingProvider()

    async with QdrantVectorStore() as store:
        vector = (await embedder.embed([chunk.text]))[0]
        await store.upsert_chunks(knowledge_base_id, [chunk], [vector])
        results = await store.search(knowledge_base_id, vector, limit=1)
        assert len(results) == 1
        assert results[0].payload["document_id"] == str(document_id)

        retrieved = await DenseRetriever(embedder, store).retrieve(
            knowledge_base_id,
            chunk.text,
            top_k=1,
            score_threshold=0.9,
        )
        context = ContextBuilder(token_budget=100).build(retrieved)
        assert len(retrieved) == 1
        assert context.citations[0].chunk_id == str(chunk.chunk_id)

        await store.delete_document(knowledge_base_id, document_id)
        assert await store.search(knowledge_base_id, vector, limit=1) == []
