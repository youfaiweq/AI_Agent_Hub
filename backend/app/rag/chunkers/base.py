"""Chunker interface."""

from abc import ABC, abstractmethod

from app.rag.contracts import Chunk, ParsedDocument


class Chunker(ABC):
    """Base interface for page-aware text chunking."""

    @abstractmethod
    def split(self, document: ParsedDocument) -> list[Chunk]:
        """Split cleaned text into traceable chunks."""
