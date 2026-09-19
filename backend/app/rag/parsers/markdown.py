"""Markdown parser."""

from pathlib import PurePath
from typing import BinaryIO
from uuid import UUID

from app.rag.contracts import ParsedDocument, ParsedPage
from app.rag.errors import DocumentProcessingError
from app.rag.parsers.base import Parser


class MarkdownParser(Parser):
    """Parse UTF-8 Markdown while preserving source markup as text."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".md", ".markdown"})

    def parse(self, file: BinaryIO, *, document_id: UUID, filename: str) -> ParsedDocument:
        try:
            raw = file.read()
            text = raw.decode("utf-8-sig")
        except AttributeError as exc:
            raise DocumentProcessingError("INVALID_FILE_STREAM", "Parser requires a binary file") from exc
        except UnicodeDecodeError as exc:
            raise DocumentProcessingError("INVALID_ENCODING", "Markdown file must be UTF-8 encoded") from exc
        return ParsedDocument(
            document_id=document_id,
            filename=PurePath(filename).name,
            content_type="text/markdown",
            pages=(ParsedPage(page_number=1, text=text),),
        )
