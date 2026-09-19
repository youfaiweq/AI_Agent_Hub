"""Embedding provider contract."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingError(ValueError):
    """Safe error raised by an embedding provider."""


class EmbeddingProvider(ABC):
    """Provider interface for batch text embeddings."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the configured vector dimension."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return a stable provider/model identifier."""

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a non-empty batch while preserving input order."""
