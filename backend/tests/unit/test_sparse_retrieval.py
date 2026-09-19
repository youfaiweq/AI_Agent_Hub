"""Unit tests for the PostgreSQL sparse-retrieval adapter."""

from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.models.document_chunk import DocumentChunk
from app.rag.retrievers.sparse import SparseRetrievalError, SparseRetriever


class FakeResult:
    def __init__(self, rows: list[tuple[DocumentChunk, str, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[DocumentChunk, str, float]]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[tuple[DocumentChunk, str, float]]) -> None:
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


@pytest.mark.asyncio
async def test_sparse_retriever_normalizes_ranked_rows_and_filters_score() -> None:
    document_id = uuid4()
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        knowledge_base_id=uuid4(),
        page_number=2,
        start_char=10,
        end_char=42,
        text="PostgreSQL full text search",
    )
    session = FakeSession([(chunk, "guide.md", 0.72), (chunk, "guide.md", 0.21)])

    results = await SparseRetriever(session).retrieve(
        chunk.knowledge_base_id,
        "postgresql search",
        top_k=3,
        score_threshold=0.5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == str(chunk.id)
    assert results[0].document_id == str(document_id)
    assert results[0].filename == "guide.md"
    assert results[0].score == 0.72
    assert results[0].start_char == 10
    assert "websearch_to_tsquery" in str(
        session.statement.compile(dialect=postgresql.dialect())
    )


@pytest.mark.asyncio
async def test_sparse_retriever_rejects_invalid_input() -> None:
    session = FakeSession([])
    retriever = SparseRetriever(session)

    with pytest.raises(SparseRetrievalError):
        await retriever.retrieve(uuid4(), "  ")
    with pytest.raises(SparseRetrievalError):
        await retriever.retrieve(uuid4(), "query", top_k=0)
    with pytest.raises(SparseRetrievalError):
        await retriever.retrieve(uuid4(), "query", score_threshold=-0.1)
