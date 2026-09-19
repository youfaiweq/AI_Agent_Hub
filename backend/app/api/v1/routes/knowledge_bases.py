"""Knowledge base CRUD endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies import SessionDependency, UserDependency
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)
from app.services.knowledge_bases import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def get_knowledge_base_service(session: SessionDependency) -> KnowledgeBaseService:
    return KnowledgeBaseService(session)


ServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]
PageDependency = Annotated[int, Query(ge=1, description="One-based page number")]
PageSizeDependency = Annotated[int, Query(ge=1, le=100, description="Items per page")]
SortByDependency = Annotated[
    Literal["created_at", "updated_at", "name"],
    Query(description="Field used for sorting"),
]
SortOrderDependency = Annotated[
    Literal["asc", "desc"],
    Query(description="Sort direction"),
]


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    user: UserDependency,
    service: ServiceDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = await service.create(user.id, payload)
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    user: UserDependency,
    service: ServiceDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    sort_by: SortByDependency = "created_at",
    sort_order: SortOrderDependency = "desc",
) -> KnowledgeBaseListResponse:
    return await service.list(user.id, page, page_size, sort_by, sort_order)


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    knowledge_base_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = await service.get(user.id, knowledge_base_id)
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    knowledge_base_id: UUID,
    payload: KnowledgeBaseUpdate,
    user: UserDependency,
    service: ServiceDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = await service.update(user.id, knowledge_base_id, payload)
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    knowledge_base_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> Response:
    await service.delete(user.id, knowledge_base_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
