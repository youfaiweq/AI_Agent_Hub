"""Parser selection by source filename."""

from pathlib import PurePath
from typing import BinaryIO
from uuid import UUID

from app.rag.contracts import ParsedDocument
from app.rag.errors import DocumentProcessingError
from app.rag.parsers.base import Parser
from app.rag.parsers.markdown import MarkdownParser
from app.rag.parsers.pdf import PdfParser
from app.rag.parsers.text import TextParser


class ParserRegistry:
    """Resolve one parser for each supported source extension."""

    def __init__(self, parsers: tuple[Parser, ...] = ()) -> None:
        self._parsers: dict[str, Parser] = {}
        for parser in parsers:
            self.register(parser)

    def register(self, parser: Parser) -> None:
        for extension in parser.supported_extensions:
            normalized = extension.lower()
            if not normalized.startswith("."):
                raise DocumentProcessingError("INVALID_EXTENSION", "Parser extensions must start with a dot")
            if normalized in self._parsers:
                raise DocumentProcessingError("DUPLICATE_PARSER", "A parser is already registered for this extension")
            self._parsers[normalized] = parser

    def get(self, filename: str) -> Parser:
        extension = PurePath(filename).suffix.lower()
        try:
            return self._parsers[extension]
        except KeyError as exc:
            raise DocumentProcessingError(
                "UNSUPPORTED_DOCUMENT_TYPE",
                "No parser is registered for this file type",
            ) from exc

    def parse(self, file: BinaryIO, *, document_id: UUID, filename: str) -> ParsedDocument:
        return self.get(filename).parse(file, document_id=document_id, filename=filename)


def build_default_registry() -> ParserRegistry:
    """Create the parser registry for the v0.3 document formats."""

    return ParserRegistry((TextParser(), MarkdownParser(), PdfParser()))
