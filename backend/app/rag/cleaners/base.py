"""Cleaner interface."""

from abc import ABC, abstractmethod

from app.rag.contracts import ParsedDocument


class Cleaner(ABC):
    """Base interface for normalized parser output."""

    @abstractmethod
    def clean(self, document: ParsedDocument) -> ParsedDocument:
        """Return a cleaned document while preserving source page numbers."""
