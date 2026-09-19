"""Embedding provider adapters."""

from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.hash import HashEmbeddingProvider

__all__ = ["EmbeddingProvider", "HashEmbeddingProvider"]
