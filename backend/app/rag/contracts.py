"""Shared parsing, cleaning, and chunking data contracts."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ParsedPage:
    """Text extracted from one logical source page."""

    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    """Normalized parser output while preserving page boundaries."""

    document_id: UUID
    filename: str
    content_type: str
    pages: tuple[ParsedPage, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return the page texts joined in source order."""

        return "\n\n".join(page.text for page in self.pages)


@dataclass(frozen=True)
class ChunkMetadata:
    """Traceability metadata attached to every chunk."""

    document_id: UUID
    filename: str
    page_number: int
    start_char: int
    end_char: int


@dataclass(frozen=True)
class Chunk:
    """A chunk of cleaned text with stable source metadata."""

    text: str
    metadata: ChunkMetadata
    chunk_id: UUID = field(default_factory=uuid4)
