"""PostgreSQL full-text sparse retrieval."""

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.rag.retrievers.base import RetrievedChunk


class SparseRetrievalError(ValueError):
    """Invalid sparse-retrieval input."""


class SparseRetriever:
    """Retrieve chunks with PostgreSQL's language-neutral full-text search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def retrieve(
        self,
        knowledge_base_id: UUID,
        query: str,
        *,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise SparseRetrievalError("query must not be empty")
        if top_k <= 0:
            raise SparseRetrievalError("top_k must be greater than zero")
        if score_threshold is not None and score_threshold < 0:
            raise SparseRetrievalError("score_threshold must not be negative")

        query_text = func.websearch_to_tsquery("simple", query.strip())
        search_vector = func.to_tsvector("simple", DocumentChunk.text)
        score = func.ts_rank_cd(search_vector, query_text).label("score")
        statement = (
            select(DocumentChunk, Document.filename, score)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.knowledge_base_id == knowledge_base_id,
                Document.status == DocumentStatus.COMPLETED,
                search_vector.op("@@")(query_text),
            )
            .order_by(desc(score), DocumentChunk.id)
            .limit(top_k)
        )
        result = await self.session.execute(statement)

        retrieved: list[RetrievedChunk] = []
        for chunk, filename, raw_score in result.all():
            normalized_score = float(raw_score)
            if score_threshold is not None and normalized_score < score_threshold:
                continue
            retrieved.append(
                RetrievedChunk(
                    chunk_id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    filename=str(filename),
                    page_number=chunk.page_number,
                    text=chunk.text,
                    score=normalized_score,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                )
            )
        return retrieved
