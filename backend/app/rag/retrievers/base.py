"""Shared retrieval result contract."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RetrievedChunk:
    """A retrieval result normalized into a citation-ready chunk."""

    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    text: str
    score: float
    start_char: int
    end_char: int


class Retriever(Protocol):
    """Provider-neutral contract shared by dense and sparse retrievers."""

    async def retrieve(
        self,
        knowledge_base_id: UUID,
        query: str,
        *,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]: ...
