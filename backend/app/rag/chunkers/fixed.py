"""Deterministic character-window chunker."""

from app.rag.chunkers.base import Chunker
from app.rag.contracts import Chunk, ChunkMetadata, ParsedDocument
from app.rag.errors import DocumentProcessingError


class FixedCharacterChunker(Chunker):
    """Split each page into fixed-size overlapping character windows."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        if chunk_size <= 0:
            raise DocumentProcessingError("INVALID_CHUNK_SIZE", "chunk_size must be greater than zero")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise DocumentProcessingError(
                "INVALID_CHUNK_OVERLAP",
                "chunk_overlap must be non-negative and smaller than chunk_size",
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        for page in document.pages:
            if not page.text:
                continue
            start = 0
            while start < len(page.text):
                end = min(start + self.chunk_size, len(page.text))
                chunks.append(
                    Chunk(
                        text=page.text[start:end],
                        metadata=ChunkMetadata(
                            document_id=document.document_id,
                            filename=document.filename,
                            page_number=page.page_number,
                            start_char=start,
                            end_char=end,
                        ),
                    )
                )
                if end == len(page.text):
                    break
                start = end - self.chunk_overlap
        return chunks
