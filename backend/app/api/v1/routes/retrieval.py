"""Retrieval debug and evaluation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import (
    EmbeddingDependency,
    ObservabilityDependency,
    RerankerDependency,
    SessionDependency,
    UserDependency,
    VectorStoreDependency,
)
from app.schemas.retrieval import (
    RetrievalDebugRequest,
    RetrievalDebugResponse,
    RetrievalEvaluationRequest,
    RetrievalEvaluationResponse,
)
from app.services.retrieval_debug import RetrievalDebugService

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/retrieval",
    tags=["retrieval"],
)


def get_retrieval_debug_service(
    session: SessionDependency,
    embedder: EmbeddingDependency,
    vector_store: VectorStoreDependency,
    reranker: RerankerDependency,
    observability: ObservabilityDependency,
) -> RetrievalDebugService:
    return RetrievalDebugService(session, embedder, vector_store, reranker, observability)


ServiceDependency = Annotated[
    RetrievalDebugService,
    Depends(get_retrieval_debug_service),
]


@router.post("/debug", response_model=RetrievalDebugResponse)
async def debug_retrieval(
    knowledge_base_id: UUID,
    payload: RetrievalDebugRequest,
    user: UserDependency,
    service: ServiceDependency,
) -> RetrievalDebugResponse:
    return await service.debug(user.id, knowledge_base_id, payload)


@router.post("/evaluate", response_model=RetrievalEvaluationResponse)
async def evaluate_retrieval(
    knowledge_base_id: UUID,
    payload: RetrievalEvaluationRequest,
    user: UserDependency,
    service: ServiceDependency,
) -> RetrievalEvaluationResponse:
    return await service.evaluate(user.id, knowledge_base_id, payload)
