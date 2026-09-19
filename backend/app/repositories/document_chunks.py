"""Persistence operations for processed document chunks."""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.rag.contracts import Chunk


class DocumentChunkRepository:
    """Replace the searchable chunk snapshot for one document."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_document(
        self,
        document_id: UUID,
        knowledge_base_id: UUID,
        chunks: list[Chunk],
    ) -> None:
        """Delete the previous snapshot and stage the newly processed chunks."""

        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        self.session.add_all(
            [
                DocumentChunk(
                    id=chunk.chunk_id,
                    document_id=document_id,
                    knowledge_base_id=knowledge_base_id,
                    page_number=chunk.metadata.page_number,
                    start_char=chunk.metadata.start_char,
                    end_char=chunk.metadata.end_char,
                    text=chunk.text,
                )
                for chunk in chunks
            ]
        )
        await self.session.flush()
