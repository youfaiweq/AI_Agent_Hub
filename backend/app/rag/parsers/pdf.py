"""PDF parser backed by pypdf."""

from io import BytesIO
from pathlib import PurePath
from typing import BinaryIO
from uuid import UUID

from pypdf import PdfReader

from app.rag.contracts import ParsedDocument, ParsedPage
from app.rag.errors import DocumentProcessingError
from app.rag.parsers.base import Parser


class PdfParser(Parser):
    """Extract text page-by-page from a PDF document."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".pdf"})

    def parse(self, file: BinaryIO, *, document_id: UUID, filename: str) -> ParsedDocument:
        try:
            raw = file.read()
            reader = PdfReader(BytesIO(raw), strict=True)
            if not reader.pages:
                raise DocumentProcessingError("EMPTY_PDF", "PDF contains no pages")
            pages = tuple(
                ParsedPage(page_number=index + 1, text=page.extract_text() or "")
                for index, page in enumerate(reader.pages)
            )
        except DocumentProcessingError:
            raise
        except AttributeError as exc:
            raise DocumentProcessingError("INVALID_FILE_STREAM", "Parser requires a binary file") from exc
        except Exception as exc:
            raise DocumentProcessingError("INVALID_PDF", "The PDF file could not be parsed") from exc
        return ParsedDocument(
            document_id=document_id,
            filename=PurePath(filename).name,
            content_type="application/pdf",
            pages=pages,
        )
