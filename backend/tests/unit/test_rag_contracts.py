"""Unit tests for parsing, cleaning, and chunking contracts."""

from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfWriter

from app.rag.chunkers.fixed import FixedCharacterChunker
from app.rag.cleaners.text import TextCleaner
from app.rag.contracts import ParsedDocument, ParsedPage
from app.rag.errors import DocumentProcessingError
from app.rag.parsers.markdown import MarkdownParser
from app.rag.parsers.pdf import PdfParser
from app.rag.parsers.registry import build_default_registry
from app.rag.parsers.text import TextParser
from app.rag.pipeline import DocumentIngestionPipeline


def test_text_and_markdown_parsers_preserve_document_identity_and_page_number() -> None:
    document_id = uuid4()
    text_document = TextParser().parse(
        BytesIO("\ufeffHello\nworld".encode("utf-8")),
        document_id=document_id,
        filename="notes.txt",
    )
    markdown_document = MarkdownParser().parse(
        BytesIO(b"# Heading\n\nBody"),
        document_id=document_id,
        filename="notes.md",
    )

    assert text_document.document_id == document_id
    assert text_document.pages == (ParsedPage(page_number=1, text="Hello\nworld"),)
    assert markdown_document.content_type == "text/markdown"
    assert markdown_document.text == "# Heading\n\nBody"


def test_pdf_parser_reads_pages_and_rejects_malformed_files() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_bytes = BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    document = PdfParser().parse(pdf_bytes, document_id=uuid4(), filename="blank.pdf")

    assert len(document.pages) == 1
    assert document.pages[0].page_number == 1
    assert document.content_type == "application/pdf"

    with pytest.raises(DocumentProcessingError, match="could not be parsed") as error_info:
        PdfParser().parse(BytesIO(b"not a PDF"), document_id=uuid4(), filename="broken.pdf")
    assert error_info.value.code == "INVALID_PDF"


def test_parser_registry_rejects_unsupported_extensions() -> None:
    registry = build_default_registry()

    assert registry.get("guide.markdown").__class__ is MarkdownParser
    with pytest.raises(DocumentProcessingError) as error_info:
        registry.get("guide.docx")
    assert error_info.value.code == "UNSUPPORTED_DOCUMENT_TYPE"


def test_text_cleaner_normalizes_whitespace_without_merging_pages() -> None:
    document = ParsedDocument(
        document_id=uuid4(),
        filename="notes.txt",
        content_type="text/plain",
        pages=(
            ParsedPage(page_number=1, text="  First  \r\n\r\n\r\nSecond\t "),
            ParsedPage(page_number=2, text=" Third \n"),
        ),
    )

    cleaned = TextCleaner().clean(document)

    assert cleaned.pages[0].text == "First\n\nSecond"
    assert cleaned.pages[1].text == "Third"
    assert [page.page_number for page in cleaned.pages] == [1, 2]


def test_fixed_chunker_emits_overlap_and_traceable_positions() -> None:
    document_id = uuid4()
    document = ParsedDocument(
        document_id=document_id,
        filename="notes.txt",
        content_type="text/plain",
        pages=(
            ParsedPage(page_number=1, text="abcdefghij"),
            ParsedPage(page_number=2, text="klmnop"),
        ),
    )

    chunks = FixedCharacterChunker(chunk_size=4, chunk_overlap=1).split(document)

    assert [chunk.text for chunk in chunks] == ["abcd", "defg", "ghij", "klmn", "nop"]
    assert [chunk.metadata.start_char for chunk in chunks] == [0, 3, 6, 0, 3]
    assert [chunk.metadata.page_number for chunk in chunks] == [1, 1, 1, 2, 2]
    assert all(chunk.metadata.document_id == document_id for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (4, 4), (4, 5), (4, -1)],
)
def test_fixed_chunker_rejects_invalid_window(chunk_size: int, chunk_overlap: int) -> None:
    with pytest.raises(DocumentProcessingError):
        FixedCharacterChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def test_ingestion_pipeline_runs_parser_cleaner_and_chunker_in_order() -> None:
    result = DocumentIngestionPipeline(
        chunker=FixedCharacterChunker(chunk_size=5, chunk_overlap=1),
    ).run(
        b"Hello\r\n\r\nworld",
        document_id=uuid4(),
        filename="guide.txt",
    )

    assert result.document.pages[0].text == "Hello\n\nworld"
    assert [chunk.text for chunk in result.chunks] == ["Hello", "o\n\nwo", "orld"]
