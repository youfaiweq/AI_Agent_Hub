"""Reciprocal Rank Fusion for dense and sparse retrieval candidates."""

from dataclasses import dataclass
from math import isfinite

from app.rag.retrievers.base import RetrievedChunk


class FusionError(ValueError):
    """Invalid fusion configuration or input."""


@dataclass(frozen=True)
class FusedRetrieval:
    """A chunk with source scores, normalized scores, and its RRF score."""

    chunk: RetrievedChunk
    fusion_score: float
    dense_score: float | None
    sparse_score: float | None
    dense_normalized_score: float | None
    sparse_normalized_score: float | None
    dense_rank: int | None
    sparse_rank: int | None


@dataclass(frozen=True)
class _RankedCandidate:
    """A de-duplicated candidate with its source rank and normalized score."""

    chunk: RetrievedChunk
    rank: int
    normalized_score: float


class RRFusion:
    """Fuse independently ranked retrieval lists using Reciprocal Rank Fusion."""

    def __init__(
        self,
        *,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> None:
        if rrf_k <= 0:
            raise FusionError("rrf_k must be greater than zero")
        if not self._valid_weight(dense_weight) or not self._valid_weight(sparse_weight):
            raise FusionError("fusion weights must be finite and greater than zero")
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

    def fuse(
        self,
        dense_results: list[RetrievedChunk],
        sparse_results: list[RetrievedChunk],
        *,
        top_k: int = 5,
    ) -> list[FusedRetrieval]:
        """Return the top fused chunks while preserving source-level evidence."""

        if top_k <= 0:
            raise FusionError("top_k must be greater than zero")

        dense_candidates = self._rank_candidates(dense_results)
        sparse_candidates = self._rank_candidates(sparse_results)
        by_chunk_id: dict[str, FusedRetrieval] = {}

        for candidate in dense_candidates:
            by_chunk_id[candidate.chunk.chunk_id] = FusedRetrieval(
                chunk=candidate.chunk,
                fusion_score=self.dense_weight / (self.rrf_k + candidate.rank),
                dense_score=candidate.chunk.score,
                sparse_score=None,
                dense_normalized_score=candidate.normalized_score,
                sparse_normalized_score=None,
                dense_rank=candidate.rank,
                sparse_rank=None,
            )

        for candidate in sparse_candidates:
            existing = by_chunk_id.get(candidate.chunk.chunk_id)
            sparse_score = self.sparse_weight / (self.rrf_k + candidate.rank)
            if existing is None:
                by_chunk_id[candidate.chunk.chunk_id] = FusedRetrieval(
                    chunk=candidate.chunk,
                    fusion_score=sparse_score,
                    dense_score=None,
                    sparse_score=candidate.chunk.score,
                    dense_normalized_score=None,
                    sparse_normalized_score=candidate.normalized_score,
                    dense_rank=None,
                    sparse_rank=candidate.rank,
                )
                continue
            by_chunk_id[candidate.chunk.chunk_id] = FusedRetrieval(
                chunk=self._merge_chunks(existing.chunk, candidate.chunk),
                fusion_score=existing.fusion_score + sparse_score,
                dense_score=existing.dense_score,
                sparse_score=candidate.chunk.score,
                dense_normalized_score=existing.dense_normalized_score,
                sparse_normalized_score=candidate.normalized_score,
                dense_rank=existing.dense_rank,
                sparse_rank=candidate.rank,
            )

        return sorted(
            by_chunk_id.values(),
            key=lambda item: (-item.fusion_score, item.chunk.chunk_id),
        )[:top_k]

    @classmethod
    def _rank_candidates(cls, results: list[RetrievedChunk]) -> list[_RankedCandidate]:
        unique: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()
        for result in results:
            if result.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(result.chunk_id)
            unique.append(result)

        if not unique:
            return []
        scores = [result.score for result in unique]
        if not all(isfinite(score) for score in scores):
            raise FusionError("retrieval scores must be finite")
        minimum = min(scores)
        maximum = max(scores)
        denominator = maximum - minimum
        normalized = [
            1.0 if denominator == 0 else (score - minimum) / denominator
            for score in scores
        ]
        return [
            _RankedCandidate(chunk=chunk, rank=rank, normalized_score=normalized_score)
            for rank, (chunk, normalized_score) in enumerate(zip(unique, normalized, strict=True), 1)
        ]

    @staticmethod
    def _merge_chunks(first: RetrievedChunk, second: RetrievedChunk) -> RetrievedChunk:
        """Prefer populated metadata from either adapter for a shared chunk."""

        return RetrievedChunk(
            chunk_id=first.chunk_id,
            document_id=first.document_id or second.document_id,
            filename=first.filename or second.filename,
            page_number=first.page_number or second.page_number,
            text=first.text or second.text,
            score=first.score,
            start_char=first.start_char or second.start_char,
            end_char=first.end_char or second.end_char,
        )

    @staticmethod
    def _valid_weight(weight: float) -> bool:
        return isfinite(weight) and weight > 0
