"""Retrieval debug orchestration service."""

import logging
from time import perf_counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.knowledge_base import KnowledgeBase
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.evaluation.metrics import evaluate_case, summarize_cases
from app.rag.rerankers.base import BaseReranker, RerankedChunk, RerankerError
from app.rag.retrievers.dense import DenseRetriever, RetrievalError
from app.rag.retrievers.hybrid import HybridRetrievalError, HybridRetrievedChunk, HybridRetriever
from app.rag.retrievers.sparse import SparseRetrievalError, SparseRetriever
from app.rag.vectorstores.qdrant import QdrantVectorStore
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.retrieval import (
    EvaluationCaseResult,
    EvaluationMetrics,
    RetrievalDebugItem,
    RetrievalDebugRequest,
    RetrievalDebugResponse,
    RetrievalEvaluationRequest,
    RetrievalEvaluationResponse,
)

logger = logging.getLogger(__name__)


class RetrievalDebugService:
    """Run retrieval stages and expose traceable result rows."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        reranker: BaseReranker,
    ) -> None:
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.dense = DenseRetriever(embedder, vector_store)
        self.sparse = SparseRetriever(session)
        self.hybrid = HybridRetriever(self.dense, self.sparse)
        self.reranker = reranker

    async def debug(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        payload: RetrievalDebugRequest,
    ) -> RetrievalDebugResponse:
        knowledge_base = await self.knowledge_bases.get_owned(knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        started = perf_counter()
        try:
            items = await self._retrieve_items(knowledge_base, payload)
        except RerankerError as exc:
            raise AppError("RERANKER_FAILED", exc.message, 502) from exc
        except (RetrievalError, SparseRetrievalError, HybridRetrievalError) as exc:
            raise AppError("RETRIEVAL_DEBUG_FAILED", str(exc), 422) from exc
        except Exception as exc:
            logger.exception(
                "Retrieval debug failed",
                extra={"knowledge_base_id": str(knowledge_base_id), "mode": payload.mode},
            )
            raise AppError("RETRIEVAL_DEBUG_FAILED", "Retrieval debug failed", 502) from exc
        logger.info(
            "Retrieval debug completed",
            extra={
                "knowledge_base_id": str(knowledge_base_id),
                "mode": payload.mode,
                "result_count": len(items),
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return RetrievalDebugResponse(
            query=payload.query,
            mode=payload.mode,
            candidate_k=payload.candidate_k,
            items=items,
        )

    async def evaluate(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        payload: RetrievalEvaluationRequest,
    ) -> RetrievalEvaluationResponse:
        case_results: list[EvaluationCaseResult] = []
        case_metrics = []
        for case in payload.dataset.cases:
            debug = await self.debug(
                user_id,
                knowledge_base_id,
                RetrievalDebugRequest(
                    query=case.question,
                    mode=payload.mode,
                    top_k=payload.top_k,
                    candidate_k=payload.candidate_k,
                ),
            )
            metrics = evaluate_case(
                case.expected_chunk_ids,
                [item.chunk_id for item in debug.items],
            )
            case_metrics.append(metrics)
            case_results.append(
                EvaluationCaseResult(
                    case_id=case.case_id,
                    question=case.question,
                    expected_chunk_ids=case.expected_chunk_ids,
                    retrieved_chunk_ids=list(metrics.retrieved_chunk_ids),
                    retrieval_hit=metrics.retrieval_hit,
                    citation_correctness=metrics.citation_correctness,
                )
            )
        retrieval_recall, citation_correctness = summarize_cases(case_metrics)
        return RetrievalEvaluationResponse(
            dataset_name=payload.dataset.name,
            dataset_version=payload.dataset.version,
            mode=payload.mode,
            metrics=EvaluationMetrics(
                total_cases=len(case_results),
                retrieval_recall=retrieval_recall,
                citation_correctness=citation_correctness,
            ),
            cases=case_results,
        )

    async def _retrieve_items(
        self,
        knowledge_base: KnowledgeBase,
        payload: RetrievalDebugRequest,
    ) -> list[RetrievalDebugItem]:
        if payload.mode == "dense":
            chunks = await self.dense.retrieve(
                knowledge_base.id,
                payload.query,
                top_k=payload.top_k,
                score_threshold=get_settings().retrieval_score_threshold,
            )
            return [self._basic_item(chunk, rank) for rank, chunk in enumerate(chunks, 1)]
        if payload.mode == "sparse":
            chunks = await self.sparse.retrieve(
                knowledge_base.id,
                payload.query,
                top_k=payload.top_k,
            )
            return [self._basic_item(chunk, rank, sparse=True) for rank, chunk in enumerate(chunks, 1)]

        hybrid = await self.hybrid.retrieve(
            knowledge_base.id,
            payload.query,
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
        )
        if payload.mode == "hybrid":
            return [self._hybrid_item(chunk, rank) for rank, chunk in enumerate(hybrid, 1)]

        reranked = await self.reranker.rerank(
            payload.query,
            hybrid,
            top_k=payload.top_k,
        )
        hybrid_by_id = {chunk.chunk_id: chunk for chunk in hybrid}
        return [
            self._reranked_item(chunk, hybrid_by_id.get(chunk.chunk_id), rank)
            for rank, chunk in enumerate(reranked, 1)
        ]

    @staticmethod
    def _basic_item(chunk, rank: int, *, sparse: bool = False) -> RetrievalDebugItem:
        return RetrievalDebugItem(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page_number=chunk.page_number,
            snippet=chunk.text,
            dense_score=None if sparse else chunk.score,
            sparse_score=chunk.score if sparse else None,
            final_rank=rank,
        )

    @staticmethod
    def _hybrid_item(chunk: HybridRetrievedChunk, rank: int) -> RetrievalDebugItem:
        return RetrievalDebugItem(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page_number=chunk.page_number,
            snippet=chunk.text,
            dense_score=chunk.dense_score,
            sparse_score=chunk.sparse_score,
            fusion_score=chunk.fusion_score,
            final_rank=rank,
        )

    @staticmethod
    def _reranked_item(
        chunk: RerankedChunk,
        hybrid: HybridRetrievedChunk | None,
        rank: int,
    ) -> RetrievalDebugItem:
        return RetrievalDebugItem(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page_number=chunk.page_number,
            snippet=chunk.text,
            dense_score=hybrid.dense_score if hybrid else None,
            sparse_score=hybrid.sparse_score if hybrid else None,
            fusion_score=hybrid.fusion_score if hybrid else None,
            rerank_score=chunk.rerank_score,
            final_rank=rank,
        )
