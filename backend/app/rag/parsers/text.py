"""Plain-text parser."""

from pathlib import PurePath
from typing import BinaryIO
from uuid import UUID

from app.rag.contracts import ParsedDocument, ParsedPage
from app.rag.errors import DocumentProcessingError
from app.rag.parsers.base import Parser


class TextParser(Parser):
    """Parse UTF-8 TXT files as one logical page."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".txt"})

    def parse(self, file: BinaryIO, *, document_id: UUID, filename: str) -> ParsedDocument:
        try:
            raw = file.read()
            text = raw.decode("utf-8-sig")
        except AttributeError as exc:
            raise DocumentProcessingError("INVALID_FILE_STREAM", "Parser requires a binary file") from exc
        except UnicodeDecodeError as exc:
            raise DocumentProcessingError("INVALID_ENCODING", "Text file must be UTF-8 encoded") from exc
        return ParsedDocument(
            document_id=document_id,
            filename=PurePath(filename).name,
            content_type="text/plain",
            pages=(ParsedPage(page_number=1, text=text),),
        )
