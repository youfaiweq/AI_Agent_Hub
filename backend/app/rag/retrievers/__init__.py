"""Retrieval adapters."""

from app.rag.retrievers.base import RetrievedChunk, Retriever
from app.rag.retrievers.dense import DenseRetriever
from app.rag.retrievers.sparse import SparseRetrievalError, SparseRetriever

__all__ = [
    "DenseRetriever",
    "HybridRetrievalError",
    "HybridRetrievedChunk",
    "HybridRetriever",
    "RetrievedChunk",
    "Retriever",
    "SparseRetrievalError",
    "SparseRetriever",
]


def __getattr__(name: str):
    """Lazily expose hybrid types to avoid the fusion/retriever import cycle."""

    if name in {"HybridRetrievedChunk", "HybridRetriever", "HybridRetrievalError"}:
        from app.rag.retrievers.hybrid import (
            HybridRetrievalError,
            HybridRetrievedChunk,
            HybridRetriever,
        )

        return {
            "HybridRetrievedChunk": HybridRetrievedChunk,
            "HybridRetriever": HybridRetriever,
            "HybridRetrievalError": HybridRetrievalError,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
