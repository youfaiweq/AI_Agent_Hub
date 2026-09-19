"""Document repository."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    """Database access constrained to a user and knowledge base scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned(
        self,
        document_id: UUID,
        user_id: UUID,
        knowledge_base_id: UUID,
    ) -> Document | None:
        result = await self.session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_owned_for_update(
        self,
        document_id: UUID,
        user_id: UUID,
        knowledge_base_id: UUID,
    ) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def count_owned(self, user_id: UUID, knowledge_base_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Document)
            .where(
                Document.user_id == user_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
        )
        return int(result.scalar_one())

    async def list_owned(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        offset: int,
        limit: int,
    ) -> list[Document]:
        result = await self.session.execute(
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .order_by(Document.created_at.desc(), Document.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
    ) -> Document:
        document = Document(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            status="processing",
        )
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)
