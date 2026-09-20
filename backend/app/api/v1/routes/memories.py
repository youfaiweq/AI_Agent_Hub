"""Explicit long-term memory endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies import ObservabilityDependency, SessionDependency, UserDependency
from app.schemas.long_term_memory import (
    MemoryCreate,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdate,
)
from app.services.long_term_memories import LongTermMemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


def get_memory_service(
    session: SessionDependency,
    observability: ObservabilityDependency,
) -> LongTermMemoryService:
    return LongTermMemoryService(session, observability)


ServiceDependency = Annotated[LongTermMemoryService, Depends(get_memory_service)]
PageDependency = Annotated[int, Query(ge=1, description="One-based page number")]
PageSizeDependency = Annotated[int, Query(ge=1, le=100, description="Items per page")]
MemoryTypeDependency = Annotated[
    Literal["fact", "preference", "instruction", "metric"] | None,
    Query(description="Filter by memory type"),
]


@router.post("/extract", response_model=MemoryExtractResponse)
async def extract_memories(
    payload: MemoryExtractRequest,
    user: UserDependency,
    service: ServiceDependency,
) -> MemoryExtractResponse:
    """Extract explicit candidates without persisting them."""

    return await service.extract(payload)


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    user: UserDependency,
    service: ServiceDependency,
) -> MemoryResponse:
    return await service.create(user.id, payload)


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    user: UserDependency,
    service: ServiceDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    query: str | None = Query(default=None, max_length=200),
    memory_type: MemoryTypeDependency = None,
) -> MemoryListResponse:
    return await service.list(user.id, page, page_size, query, memory_type)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    payload: MemoryUpdate,
    user: UserDependency,
    service: ServiceDependency,
) -> MemoryResponse:
    return await service.update(user.id, memory_id, payload)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> Response:
    await service.delete(user.id, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
