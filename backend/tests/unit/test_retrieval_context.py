"""Unit tests for dense retrieval and context construction."""

from uuid import uuid4

import pytest

from app.rag.context.builder import ContextBuilder
from app.rag.embeddings.hash import HashEmbeddingProvider
from app.rag.retrievers.dense import DenseRetriever, RetrievalError
from app.rag.vectorstores.qdrant import VectorSearchResult


class FakeVectorStore:
    async def search(self, knowledge_base_id, query_vector, limit=5):
        return [
            VectorSearchResult(
                point_id="point-1",
                score=0.95,
                payload={
                    "chunk_id": "chunk-1",
                    "document_id": "doc-1",
                    "filename": "guide.md",
                    "page_number": 1,
                    "start_char": 0,
                    "end_char": 20,
                    "text": "AgentHub setup instructions",
                },
            ),
            VectorSearchResult(
                point_id="point-duplicate",
                score=0.90,
                payload={
                    "chunk_id": "chunk-1",
                    "document_id": "doc-1",
                    "filename": "guide.md",
                    "page_number": 1,
                    "start_char": 0,
                    "end_char": 20,
                    "text": "AgentHub setup instructions",
                },
            ),
            VectorSearchResult(
                point_id="point-2",
                score=0.30,
                payload={
                    "chunk_id": "chunk-2",
                    "document_id": "doc-2",
                    "filename": "faq.txt",
                    "page_number": 2,
                    "start_char": 4,
                    "end_char": 18,
                    "text": "Support details",
                },
            ),
        ][:limit]


@pytest.mark.asyncio
async def test_dense_retriever_filters_threshold_and_deduplicates() -> None:
    retriever = DenseRetriever(HashEmbeddingProvider(dimension=8), FakeVectorStore())

    results = await retriever.retrieve(uuid4(), "setup", top_k=3, score_threshold=0.5)

    assert [result.chunk_id for result in results] == ["chunk-1"]
    with pytest.raises(RetrievalError):
        await retriever.retrieve(uuid4(), "", top_k=3)


def test_context_builder_respects_budget_and_emits_citations() -> None:
    chunk = DenseRetriever._normalize(
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "filename": "guide.md",
            "page_number": 3,
            "start_char": 0,
            "end_char": 100,
            "text": "A very long source passage that must be truncated.",
        },
        "chunk-1",
        0.9,
    )
    result = ContextBuilder(token_budget=8, chars_per_token=4).build([chunk])

    assert result.used_tokens <= 8
    assert len(result.citations) == 1
    assert result.citations[0].document_id == "doc-1"
    assert result.citations[0].page_number == 3
    assert result.truncated is True
