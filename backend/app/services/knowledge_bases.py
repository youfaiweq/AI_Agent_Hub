"""Knowledge base application service."""

from typing import Literal
from uuid import UUID

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)


class KnowledgeBaseService:
    """Coordinate CRUD and ownership checks for knowledge bases."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.knowledge_bases = KnowledgeBaseRepository(session)

    async def create(self, user_id: UUID, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        knowledge_base = await self.knowledge_bases.create(user_id, payload.name, payload.description)
        await self.session.commit()
        return knowledge_base

    async def list(
        self,
        user_id: UUID,
        page: int,
        page_size: int,
        sort_by: Literal["created_at", "updated_at", "name"],
        sort_order: Literal["asc", "desc"],
    ) -> KnowledgeBaseListResponse:
        sort_column = getattr(KnowledgeBase, sort_by)
        order_clause = asc(sort_column) if sort_order == "asc" else desc(sort_column)
        statement = select(KnowledgeBase).order_by(order_clause, KnowledgeBase.id)
        total = await self.knowledge_bases.count_owned(user_id)
        items = await self.knowledge_bases.list_owned(
            user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            statement=statement,
        )
        return KnowledgeBaseListResponse(
            items=[KnowledgeBaseResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get(self, user_id: UUID, knowledge_base_id: UUID) -> KnowledgeBase:
        knowledge_base = await self.knowledge_bases.get_owned(knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        return knowledge_base

    async def update(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        payload: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        knowledge_base = await self.get(user_id, knowledge_base_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(knowledge_base, field, value)
        await self.session.commit()
        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def delete(self, user_id: UUID, knowledge_base_id: UUID) -> None:
        knowledge_base = await self.get(user_id, knowledge_base_id)
        await self.knowledge_bases.delete(knowledge_base)
        await self.session.commit()
