"""Reranker provider contracts."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.retrievers.base import RetrievedChunk


class RerankerError(RuntimeError):
    """Normalized reranker configuration, request, timeout, or response error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RerankedChunk(RetrievedChunk):
    """A retrieved chunk ordered by a reranker relevance score."""

    rerank_score: float | None
    original_score: float
    used_fallback: bool


class BaseReranker(ABC):
    """Provider-neutral contract for reranking retrieved chunks."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        *,
        top_k: int | None = None,
    ) -> list[RerankedChunk]:
        """Return at most ``top_k`` chunks ordered by relevance."""
