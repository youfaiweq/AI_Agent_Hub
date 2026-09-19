"""Contract tests for RRF fusion and hybrid retrieval."""

from uuid import uuid4

import pytest

from app.rag.fusion.rrf import FusionError, RRFusion
from app.rag.retrievers.base import RetrievedChunk
from app.rag.retrievers.hybrid import HybridRetrievalError, HybridRetriever


def make_chunk(chunk_id: str, score: float, text: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=f"document-{chunk_id}",
        filename=f"{chunk_id}.md",
        page_number=1,
        text=text or f"text for {chunk_id}",
        score=score,
        start_char=0,
        end_char=10,
    )


def test_rrf_fusion_normalizes_scores_and_deduplicates_candidates() -> None:
    fusion = RRFusion(rrf_k=1)

    results = fusion.fuse(
        [make_chunk("a", 0.9), make_chunk("a", 0.8), make_chunk("b", 0.5)],
        [make_chunk("b", 0.95), make_chunk("c", 0.4), make_chunk("a", 0.2)],
        top_k=3,
    )

    assert [result.chunk.chunk_id for result in results] == ["b", "a", "c"]
    assert results[0].dense_rank == 2
    assert results[0].sparse_rank == 1
    assert results[0].dense_normalized_score == 0.0
    assert results[0].sparse_normalized_score == 1.0
    assert results[1].dense_rank == 1
    assert results[1].sparse_rank == 3
    assert 0.0 <= results[1].dense_normalized_score <= 1.0
    assert results[1].fusion_score == pytest.approx(1 / 2 + 1 / 4)


def test_rrf_fusion_rejects_invalid_configuration_and_scores() -> None:
    with pytest.raises(FusionError):
        RRFusion(rrf_k=0)
    with pytest.raises(FusionError):
        RRFusion(dense_weight=0)
    with pytest.raises(FusionError):
        RRFusion().fuse([make_chunk("a", float("inf"))], [], top_k=1)


class FakeRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def retrieve(self, knowledge_base_id, query, *, top_k=5, score_threshold=None):
        self.calls.append(
            {
                "knowledge_base_id": knowledge_base_id,
                "query": query,
                "top_k": top_k,
                "score_threshold": score_threshold,
            }
        )
        return self.results


@pytest.mark.asyncio
async def test_hybrid_retriever_uses_candidate_k_and_returns_fusion_evidence() -> None:
    knowledge_base_id = uuid4()
    dense = FakeRetriever([make_chunk("dense", 0.8), make_chunk("shared", 0.7)])
    sparse = FakeRetriever([make_chunk("shared", 0.95), make_chunk("sparse", 0.4)])

    results = await HybridRetriever(dense, sparse, RRFusion(rrf_k=10)).retrieve(
        knowledge_base_id,
        "retrieval query",
        top_k=2,
        candidate_k=4,
        dense_score_threshold=0.2,
        sparse_score_threshold=0.1,
    )

    assert len(results) == 2
    assert results[0].chunk_id == "shared"
    assert results[0].score == results[0].fusion_score
    assert results[0].dense_score == 0.7
    assert results[0].sparse_score == 0.95
    assert results[0].dense_rank == 2
    assert results[0].sparse_rank == 1
    assert dense.calls[0]["top_k"] == 4
    assert sparse.calls[0]["top_k"] == 4
    assert dense.calls[0]["score_threshold"] == 0.2
    assert sparse.calls[0]["score_threshold"] == 0.1


@pytest.mark.asyncio
async def test_hybrid_retriever_rejects_invalid_input() -> None:
    retriever = HybridRetriever(FakeRetriever([]), FakeRetriever([]))

    with pytest.raises(HybridRetrievalError):
        await retriever.retrieve(uuid4(), " ")
    with pytest.raises(HybridRetrievalError):
        await retriever.retrieve(uuid4(), "query", top_k=0)
    with pytest.raises(HybridRetrievalError):
        await retriever.retrieve(uuid4(), "query", top_k=3, candidate_k=2)
