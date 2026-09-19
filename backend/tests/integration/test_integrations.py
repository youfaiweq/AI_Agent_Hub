"""Integration tests for the running infrastructure adapters."""

from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import dispose_engine, get_engine, get_session_factory
from app.integrations.minio import MinioAdapter
from app.integrations.qdrant import QdrantAdapter
from app.integrations.redis import RedisAdapter
from app.models.agent import AgentRunStatus, ToolCallStatus
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.rag.context.builder import ContextBuilder
from app.rag.contracts import Chunk, ChunkMetadata
from app.rag.embeddings.hash import HashEmbeddingProvider
from app.rag.retrievers.dense import DenseRetriever
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.retrievers.sparse import SparseRetriever
from app.rag.vectorstores.qdrant import QdrantVectorStore
from app.repositories.agent_runs import AgentRunRepository, ToolCallRepository
from app.tools.registry import ToolContext
from app.tools.sql import SqlQueryTool


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_sparse_retriever_round_trip() -> None:
    email = f"sparse-{uuid4()}@example.com"
    user_id = uuid4()
    knowledge_base_id = uuid4()
    document_id = uuid4()
    user = User(id=user_id, email=email, password_hash="test-only")
    knowledge_base = KnowledgeBase(id=knowledge_base_id, user_id=user_id, name="Sparse Search")
    document = Document(
        id=document_id,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        filename="postgres.md",
        content_type="text/markdown",
        size_bytes=35,
        storage_key=f"test/{uuid4()}.md",
        status=DocumentStatus.COMPLETED,
        chunk_count=1,
    )
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        knowledge_base_id=knowledge_base_id,
        page_number=1,
        start_char=0,
        end_char=35,
        text="PostgreSQL full text retrieval works.",
    )

    async with get_session_factory()() as session:
        session.add(user)
        await session.flush()
        session.add(knowledge_base)
        await session.flush()
        session.add(document)
        await session.flush()
        session.add(chunk)
        await session.commit()
        try:
            results = await SparseRetriever(session).retrieve(
                knowledge_base_id,
                "PostgreSQL retrieval",
                top_k=3,
            )
            assert len(results) == 1
            assert results[0].document_id == str(document.id)
            assert results[0].filename == "postgres.md"
            assert results[0].score > 0
            assert await SparseRetriever(session).retrieve(uuid4(), "PostgreSQL") == []
        finally:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
    await dispose_engine()
    get_engine.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dense_sparse_hybrid_release_gate_round_trip() -> None:
    user_id = uuid4()
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    user = User(id=user_id, email=f"release-gate-{user_id}@example.com", password_hash="test-only")
    knowledge_base = KnowledgeBase(id=knowledge_base_id, user_id=user_id, name="Release Gate")
    document = Document(
        id=document_id,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        filename="release-gate.md",
        content_type="text/markdown",
        size_bytes=48,
        storage_key=f"test/{uuid4()}.md",
        status=DocumentStatus.COMPLETED,
        chunk_count=1,
    )
    chunk = Chunk(
        chunk_id=chunk_id,
        text="PostgreSQL hybrid retrieval release gate",
        metadata=ChunkMetadata(
            document_id=document_id,
            filename="release-gate.md",
            page_number=1,
            start_char=0,
            end_char=48,
        ),
    )
    searchable_chunk = DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        knowledge_base_id=knowledge_base_id,
        page_number=1,
        start_char=0,
        end_char=48,
        text=chunk.text,
    )
    embedder = HashEmbeddingProvider()

    async with get_session_factory()() as session:
        try:
            session.add(user)
            await session.flush()
            session.add(knowledge_base)
            await session.flush()
            session.add(document)
            await session.flush()
            session.add(searchable_chunk)
            await session.commit()

            async with QdrantVectorStore() as vector_store:
                vector = (await embedder.embed([chunk.text]))[0]
                await vector_store.upsert_chunks(knowledge_base_id, [chunk], [vector])
                dense_results = await DenseRetriever(embedder, vector_store).retrieve(
                    knowledge_base_id,
                    "PostgreSQL hybrid retrieval",
                    top_k=1,
                )
                sparse_results = await SparseRetriever(session).retrieve(
                    knowledge_base_id,
                    "PostgreSQL hybrid retrieval",
                    top_k=1,
                )
                hybrid_results = await HybridRetriever(
                    DenseRetriever(embedder, vector_store),
                    SparseRetriever(session),
                ).retrieve(
                    knowledge_base_id,
                    "PostgreSQL hybrid retrieval",
                    top_k=1,
                    candidate_k=2,
                )
                assert dense_results[0].chunk_id == str(chunk_id)
                assert sparse_results[0].chunk_id == str(chunk_id)
                assert hybrid_results[0].chunk_id == str(chunk_id)
                assert hybrid_results[0].dense_score is not None
                assert hybrid_results[0].sparse_score is not None
                await vector_store.delete_document(knowledge_base_id, document_id)
        finally:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
    await dispose_engine()
    get_engine.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_runtime_records_persist_and_update() -> None:
    user_id = uuid4()
    agent_id = uuid4()
    async with get_session_factory()() as session:
        try:
            session.add(
                User(
                    id=user_id,
                    email=f"agent-runtime-{user_id}@example.com",
                    password_hash="test-only",
                )
            )
            await session.flush()
            runs = AgentRunRepository(session)
            tool_calls = ToolCallRepository(session)
            run = await runs.create(
                user_id=user_id,
                agent_id=agent_id,
                input_text="Run the runtime contract",
                max_steps=3,
                timeout_seconds=5,
                state={"status": "pending", "step_count": 0},
            )
            await runs.update_state(
                run,
                status=AgentRunStatus.RUNNING,
                state={"status": "running", "step_count": 1},
                step_count=1,
            )
            record = await tool_calls.create(
                agent_run_id=run.id,
                call_id="call-1",
                tool_name="contract-test",
                arguments={"value": 1},
            )
            await tool_calls.update_status(
                record,
                status=ToolCallStatus.COMPLETED,
                result={"value": 2},
                duration_ms=1.5,
            )
            await runs.update_state(
                run,
                status=AgentRunStatus.COMPLETED,
                state={"status": "completed", "step_count": 1},
                step_count=1,
            )
            await session.commit()

            loaded = await runs.get_owned(run.id, user_id)
            assert loaded is not None
            assert loaded.status == AgentRunStatus.COMPLETED
            assert loaded.step_count == 1
            assert record.status == ToolCallStatus.COMPLETED
            assert record.result == {"value": 2}
        finally:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
    await dispose_engine()
    get_engine.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sql_query_tool_runs_whitelisted_select_against_postgresql() -> None:
    user_id = uuid4()
    email = f"sql-tool-{user_id}@example.com"
    async with get_session_factory()() as session:
        try:
            session.add(User(id=user_id, email=email, password_hash="test-only"))
            await session.flush()
            tool = SqlQueryTool(session, allowed_tables={"users"}, row_limit=1)
            result = await tool.execute(
                {"query": f"SELECT email FROM users WHERE id = '{user_id}'"},
                ToolContext(user_id, None, uuid4(), None, {}),
            )
            assert result["rows"] == [{"email": email}]
        finally:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
    await dispose_engine()
    get_engine.cache_clear()
