"""Knowledge base repository."""

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    """Database access constrained to a user-owned knowledge base scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned(self, knowledge_base_id: UUID, user_id: UUID) -> KnowledgeBase | None:
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_owned(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
        )
        return int(result.scalar_one())

    async def list_owned(
        self,
        user_id: UUID,
        offset: int,
        limit: int,
        statement: Select[tuple[KnowledgeBase]],
    ) -> list[KnowledgeBase]:
        result = await self.session.execute(
            statement.where(KnowledgeBase.user_id == user_id).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, user_id: UUID, name: str, description: str | None) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(user_id=user_id, name=name, description=description)
        self.session.add(knowledge_base)
        await self.session.flush()
        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def delete(self, knowledge_base: KnowledgeBase) -> None:
        await self.session.delete(knowledge_base)
