"""Document parsers."""

from app.rag.parsers.base import Parser
from app.rag.parsers.markdown import MarkdownParser
from app.rag.parsers.pdf import PdfParser
from app.rag.parsers.registry import ParserRegistry, build_default_registry
from app.rag.parsers.text import TextParser

__all__ = ["MarkdownParser", "Parser", "ParserRegistry", "PdfParser", "TextParser", "build_default_registry"]
