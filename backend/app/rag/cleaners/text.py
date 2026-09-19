"""Whitespace cleaner for text-like parser output."""

import re

from app.rag.cleaners.base import Cleaner
from app.rag.contracts import ParsedDocument, ParsedPage


class TextCleaner(Cleaner):
    """Normalize line endings, trailing whitespace, and excessive blank lines."""

    _blank_lines = re.compile(r"\n{3,}")

    def clean(self, document: ParsedDocument) -> ParsedDocument:
        pages = tuple(
            ParsedPage(page_number=page.page_number, text=self._clean_text(page.text))
            for page in document.pages
        )
        return ParsedDocument(
            document_id=document.document_id,
            filename=document.filename,
            content_type=document.content_type,
            pages=pages,
            metadata=document.metadata,
        )

    def _clean_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        lines = [line.rstrip(" \t") for line in normalized.split("\n")]
        return self._blank_lines.sub("\n\n", "\n".join(lines)).strip()
