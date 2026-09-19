"""Deterministic local hashing embedding provider for development."""

import hashlib
import math
import re
from collections.abc import Sequence

from app.rag.embeddings.base import EmbeddingError, EmbeddingProvider


class HashEmbeddingProvider(EmbeddingProvider):
    """Generate deterministic lexical vectors without an external model service.

    This adapter is an explicit local baseline, not a semantic model. It keeps
    the provider contract runnable until a configured embedding provider is
    selected for production retrieval quality.
    """

    _token_pattern = re.compile(r"\w+", re.UNICODE)

    def __init__(self, dimension: int = 384, model_name: str = "hash-v1") -> None:
        if dimension <= 0:
            raise EmbeddingError("embedding dimension must be greater than zero")
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("embedding input text must not be empty")
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        tokens = self._token_pattern.findall(text.casefold())
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            raise EmbeddingError("embedding input text contains no indexable tokens")
        return [value / norm for value in vector]
