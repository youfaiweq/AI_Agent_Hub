"""User-scoped long-term memory repository."""

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.long_term_memory import LongTermMemory


class LongTermMemoryRepository:
    """Persist and query memories within one authenticated user's scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        content: str,
        memory_type: str,
        source: str,
        confidence: float,
    ) -> LongTermMemory:
        memory = LongTermMemory(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            source=source,
            confidence=confidence,
        )
        self.session.add(memory)
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def get_owned(self, memory_id: UUID, user_id: UUID) -> LongTermMemory | None:
        result = await self.session.execute(
            select(LongTermMemory).where(
                LongTermMemory.id == memory_id,
                LongTermMemory.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_owned(
        self,
        user_id: UUID,
        query: str | None = None,
        memory_type: str | None = None,
    ) -> int:
        statement = self._owned_statement(user_id, query, memory_type)
        result = await self.session.execute(
            select(func.count()).select_from(statement.subquery())
        )
        return int(result.scalar_one())

    async def list_owned(
        self,
        user_id: UUID,
        offset: int,
        limit: int,
        query: str | None = None,
        memory_type: str | None = None,
    ) -> list[LongTermMemory]:
        statement = self._owned_statement(user_id, query, memory_type).order_by(
            LongTermMemory.updated_at.desc(), LongTermMemory.id
        )
        result = await self.session.execute(statement.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def delete(self, memory: LongTermMemory) -> None:
        await self.session.delete(memory)

    @staticmethod
    def _owned_statement(
        user_id: UUID,
        query: str | None,
        memory_type: str | None,
    ) -> Select[tuple[LongTermMemory]]:
        statement = select(LongTermMemory).where(LongTermMemory.user_id == user_id)
        if query:
            statement = statement.where(LongTermMemory.content.ilike(f"%{query}%"))
        if memory_type:
            statement = statement.where(LongTermMemory.memory_type == memory_type)
        return statement
