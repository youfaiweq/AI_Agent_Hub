"""Synchronous document parsing, cleaning, and chunking pipeline."""

from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from app.rag.chunkers.base import Chunker
from app.rag.chunkers.fixed import FixedCharacterChunker
from app.rag.cleaners.base import Cleaner
from app.rag.cleaners.text import TextCleaner
from app.rag.contracts import Chunk, ParsedDocument
from app.rag.parsers.registry import ParserRegistry, build_default_registry


@dataclass(frozen=True)
class IngestionResult:
    """Output of one synchronous document-ingestion run."""

    document: ParsedDocument
    chunks: tuple[Chunk, ...]


class DocumentIngestionPipeline:
    """Run Parser → Cleaner → Chunker with replaceable contracts."""

    def __init__(
        self,
        parser_registry: ParserRegistry | None = None,
        cleaner: Cleaner | None = None,
        chunker: Chunker | None = None,
    ) -> None:
        self.parser_registry = parser_registry or build_default_registry()
        self.cleaner = cleaner or TextCleaner()
        self.chunker = chunker or FixedCharacterChunker()

    def run(
        self,
        content: bytes,
        *,
        document_id: UUID,
        filename: str,
    ) -> IngestionResult:
        parsed = self.parser_registry.parse(
            BytesIO(content),
            document_id=document_id,
            filename=filename,
        )
        cleaned = self.cleaner.clean(parsed)
        chunks = tuple(self.chunker.split(cleaned))
        return IngestionResult(document=cleaned, chunks=chunks)
