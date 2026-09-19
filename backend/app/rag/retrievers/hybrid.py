"""Hybrid dense and sparse retrieval."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.rag.fusion.rrf import FusedRetrieval, RRFusion
from app.rag.retrievers.base import RetrievedChunk, Retriever


class HybridRetrievalError(ValueError):
    """Invalid hybrid-retrieval input."""


@dataclass(frozen=True)
class HybridRetrievedChunk(RetrievedChunk):
    """A citation-ready chunk enriched with dense/sparse retrieval evidence."""

    fusion_score: float
    dense_score: float | None
    sparse_score: float | None
    dense_normalized_score: float | None
    sparse_normalized_score: float | None
    dense_rank: int | None
    sparse_rank: int | None


class HybridRetriever:
    """Retrieve candidates from both providers and fuse them with RRF."""

    def __init__(
        self,
        dense_retriever: Retriever,
        sparse_retriever: Retriever,
        fusion: RRFusion | None = None,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.fusion = fusion or RRFusion()

    async def retrieve(
        self,
        knowledge_base_id: UUID,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int = 20,
        dense_score_threshold: float | None = None,
        sparse_score_threshold: float | None = None,
    ) -> list[HybridRetrievedChunk]:
        if not query.strip():
            raise HybridRetrievalError("query must not be empty")
        if top_k <= 0:
            raise HybridRetrievalError("top_k must be greater than zero")
        if candidate_k < top_k:
            raise HybridRetrievalError("candidate_k must be greater than or equal to top_k")

        dense_results, sparse_results = await asyncio.gather(
            self.dense_retriever.retrieve(
                knowledge_base_id,
                query,
                top_k=candidate_k,
                score_threshold=dense_score_threshold,
            ),
            self.sparse_retriever.retrieve(
                knowledge_base_id,
                query,
                top_k=candidate_k,
                score_threshold=sparse_score_threshold,
            ),
        )
        fused = self.fusion.fuse(dense_results, sparse_results, top_k=top_k)
        return [self._to_hybrid_result(result) for result in fused]

    @staticmethod
    def _to_hybrid_result(result: FusedRetrieval) -> HybridRetrievedChunk:
        chunk = result.chunk
        return HybridRetrievedChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page_number=chunk.page_number,
            text=chunk.text,
            score=result.fusion_score,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            fusion_score=result.fusion_score,
            dense_score=result.dense_score,
            sparse_score=result.sparse_score,
            dense_normalized_score=result.dense_normalized_score,
            sparse_normalized_score=result.sparse_normalized_score,
            dense_rank=result.dense_rank,
            sparse_rank=result.sparse_rank,
        )
