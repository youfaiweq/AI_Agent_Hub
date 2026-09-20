"""Tests for retrieval debug normalization and evaluation metrics."""

from uuid import uuid4

import pytest

from app.models.knowledge_base import KnowledgeBase
from app.rag.evaluation.metrics import evaluate_case, summarize_cases
from app.rag.rerankers.base import RerankedChunk
from app.rag.retrievers.base import RetrievedChunk
from app.rag.retrievers.hybrid import HybridRetrievedChunk
from app.schemas.retrieval import RetrievalDebugRequest, RetrievalEvaluationRequest
from app.services.retrieval_debug import RetrievalDebugService


def chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=f"document-{chunk_id}",
        filename=f"{chunk_id}.md",
        page_number=1,
        text=f"text {chunk_id}",
        score=score,
        start_char=0,
        end_char=10,
    )


class FakeKnowledgeBases:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    async def get_owned(self, knowledge_base_id, user_id):
        if knowledge_base_id == self.knowledge_base.id and user_id == self.knowledge_base.user_id:
            return self.knowledge_base
        return None


class FakeRetriever:
    def __init__(self, results):
        self.results = results

    async def retrieve(self, *args, **kwargs):
        return self.results


class FakeReranker:
    async def rerank(self, query, chunks, *, top_k=None):
        chunk = chunks[-1]
        return [
            RerankedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                filename=chunk.filename,
                page_number=chunk.page_number,
                text=chunk.text,
                score=0.97,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                rerank_score=0.97,
                original_score=chunk.score,
                used_fallback=False,
            )
        ][:top_k]


def make_service(knowledge_base: KnowledgeBase) -> RetrievalDebugService:
    service = RetrievalDebugService(None, None, None, FakeReranker())
    service.knowledge_bases = FakeKnowledgeBases(knowledge_base)
    dense = chunk("dense", 0.8)
    sparse = chunk("sparse", 0.7)
    shared = HybridRetrievedChunk(
        **chunk("shared", 0.6).__dict__,
        fusion_score=0.12,
        dense_score=0.6,
        sparse_score=0.5,
        dense_normalized_score=1.0,
        sparse_normalized_score=0.8,
        dense_rank=1,
        sparse_rank=2,
    )
    service.dense = FakeRetriever([dense])
    service.sparse = FakeRetriever([sparse])
    service.hybrid = FakeRetriever([shared])
    return service


@pytest.mark.asyncio
async def test_retrieval_debug_returns_traceable_scores() -> None:
    user_id = uuid4()
    knowledge_base = KnowledgeBase(id=uuid4(), user_id=user_id, name="Debug")
    service = make_service(knowledge_base)

    response = await service.debug(
        user_id,
        knowledge_base.id,
        RetrievalDebugRequest(query="question", mode="hybrid", top_k=1),
    )

    assert response.items[0].chunk_id == "shared"
    assert response.items[0].dense_score == 0.6
    assert response.items[0].sparse_score == 0.5
    assert response.items[0].fusion_score == 0.12
    assert response.items[0].final_rank == 1


@pytest.mark.asyncio
async def test_retrieval_debug_rerank_preserves_upstream_scores() -> None:
    user_id = uuid4()
    knowledge_base = KnowledgeBase(id=uuid4(), user_id=user_id, name="Debug")
    service = make_service(knowledge_base)

    response = await service.debug(
        user_id,
        knowledge_base.id,
        RetrievalDebugRequest(query="question", mode="rerank", top_k=1),
    )

    assert response.items[0].rerank_score == 0.97
    assert response.items[0].fusion_score == 0.12
    assert response.items[0].dense_score == 0.6


@pytest.mark.asyncio
async def test_evaluation_computes_recall_and_citation_correctness() -> None:
    user_id = uuid4()
    knowledge_base = KnowledgeBase(id=uuid4(), user_id=user_id, name="Evaluation")
    service = make_service(knowledge_base)
    payload = RetrievalEvaluationRequest(
        dataset={
            "name": "smoke",
            "version": "1",
            "cases": [
                {"case_id": "hit", "question": "one", "expected_chunk_ids": ["shared"]},
                {"case_id": "miss", "question": "two", "expected_chunk_ids": ["missing"]},
            ],
        },
        mode="hybrid",
        top_k=1,
    )

    response = await service.evaluate(user_id, knowledge_base.id, payload)
    repeated = await service.evaluate(user_id, knowledge_base.id, payload)

    assert response.metrics.total_cases == 2
    assert response.metrics.retrieval_recall == 0.5
    assert response.metrics.citation_correctness == 0.5
    assert repeated == response


def test_evaluation_metrics_deduplicate_citations() -> None:
    hit = evaluate_case(["a"], ["a", "a", "b"])
    miss = evaluate_case(["a"], ["b"])

    assert hit.retrieval_hit is True
    assert hit.citation_correctness == 0.5
    assert summarize_cases([hit, miss]) == (0.5, 0.25)


def test_evaluation_scores_answer_relevance_and_faithfulness() -> None:
    result = evaluate_case(
        ["launch"],
        ["launch"],
        expected_answer="The launch date is Friday.",
        answer="The launch date is Friday.",
        context_text="The launch date is Friday.",
        citation_chunk_ids=["launch"],
    )

    assert result.answer_relevance == 1.0
    assert result.faithfulness == 1.0
    assert result.retrieval_recall == 1.0
