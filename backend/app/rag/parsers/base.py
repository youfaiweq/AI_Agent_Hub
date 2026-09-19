"""Parser interface."""

from abc import ABC, abstractmethod
from typing import BinaryIO
from uuid import UUID

from app.rag.contracts import ParsedDocument


class Parser(ABC):
    """Base interface for file-to-text parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Return lowercase extensions handled by this parser."""

    @abstractmethod
    def parse(self, file: BinaryIO, *, document_id: UUID, filename: str) -> ParsedDocument:
        """Parse a binary source file into a page-aware document."""
