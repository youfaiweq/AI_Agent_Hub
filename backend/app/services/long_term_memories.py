"""Explicit long-term memory application service."""

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.memory.long_term import ExplicitMemoryExtractor
from app.repositories.long_term_memories import LongTermMemoryRepository
from app.schemas.long_term_memory import (
    MemoryCandidate,
    MemoryCreate,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdate,
)


class LongTermMemoryService:
    """Coordinate explicit extraction and user-owned memory CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.memories = LongTermMemoryRepository(session)
        self.extractor = ExplicitMemoryExtractor()

    async def create(self, user_id: UUID, payload: MemoryCreate) -> MemoryResponse:
        memory = await self.memories.create(
            user_id,
            payload.content,
            payload.memory_type,
            payload.source,
            payload.confidence,
        )
        await self.session.commit()
        return MemoryResponse.model_validate(memory)

    async def list(
        self,
        user_id: UUID,
        page: int,
        page_size: int,
        query: str | None,
        memory_type: Literal["fact", "preference", "instruction", "metric"] | None,
    ) -> MemoryListResponse:
        total = await self.memories.count_owned(user_id, query, memory_type)
        items = await self.memories.list_owned(
            user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            query=query,
            memory_type=memory_type,
        )
        return MemoryListResponse(
            items=[MemoryResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def extract(self, payload: MemoryExtractRequest) -> MemoryExtractResponse:
        candidates = [
            MemoryCandidate(
                content=item.content,
                memory_type=item.memory_type,
                source=item.source,
                confidence=item.confidence,
            )
            for item in self.extractor.extract(payload.text)
        ]
        return MemoryExtractResponse(
            candidates=candidates,
            requires_confirmation=bool(candidates),
        )

    async def update(
        self,
        user_id: UUID,
        memory_id: UUID,
        payload: MemoryUpdate,
    ) -> MemoryResponse:
        memory = await self.memories.get_owned(memory_id, user_id)
        if memory is None:
            raise AppError("MEMORY_NOT_FOUND", "Memory was not found", 404)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(memory, field, value.strip() if isinstance(value, str) else value)
        await self.session.commit()
        await self.session.refresh(memory)
        return MemoryResponse.model_validate(memory)

    async def delete(self, user_id: UUID, memory_id: UUID) -> None:
        memory = await self.memories.get_owned(memory_id, user_id)
        if memory is None:
            raise AppError("MEMORY_NOT_FOUND", "Memory was not found", 404)
        await self.memories.delete(memory)
        await self.session.commit()
