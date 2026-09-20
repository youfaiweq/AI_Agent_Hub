"""Agent configuration, execution, and history endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.core.config import get_settings
from app.core.dependencies import (
    EmbeddingDependency,
    ObservabilityDependency,
    SessionDependency,
    UserDependency,
    VectorStoreDependency,
)
from app.rag.llms.base import LLMProvider
from app.rag.llms.openai_compatible import OpenAICompatibleLLMProvider
from app.schemas.agents import (
    AgentCreate,
    AgentResponse,
    AgentRunCreate,
    AgentRunListResponse,
    AgentRunResponse,
    AgentUpdate,
)
from app.services.agents import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service(session: SessionDependency) -> AgentService:
    return AgentService(session)


def get_agent_runtime_service(
    session: SessionDependency,
    embedder: EmbeddingDependency,
    vector_store: VectorStoreDependency,
    observability: ObservabilityDependency,
) -> AgentService:
    settings = get_settings()
    llm: LLMProvider = OpenAICompatibleLLMProvider(settings=settings)
    return AgentService(session, llm, embedder, vector_store, settings, observability)


ServiceDependency = Annotated[AgentService, Depends(get_agent_service)]
RuntimeServiceDependency = Annotated[AgentService, Depends(get_agent_runtime_service)]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    user: UserDependency,
    service: ServiceDependency,
) -> AgentResponse:
    return await service.create(user.id, payload)


@router.get("", response_model=list[AgentResponse])
async def list_agents(user: UserDependency, service: ServiceDependency) -> list[AgentResponse]:
    return await service.list_agents(user.id)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, user: UserDependency, service: ServiceDependency) -> AgentResponse:
    return AgentResponse.model_validate(await service.get(user.id, agent_id))


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    user: UserDependency,
    service: ServiceDependency,
) -> AgentResponse:
    return await service.update(user.id, agent_id, payload)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, user: UserDependency, service: ServiceDependency) -> Response:
    await service.delete(user.id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{agent_id}/runs", response_model=AgentRunResponse)
async def run_agent(
    agent_id: UUID,
    payload: AgentRunCreate,
    user: UserDependency,
    service: RuntimeServiceDependency,
) -> AgentRunResponse:
    return await service.run(
        user.id,
        agent_id,
        payload.message,
        payload.conversation_id,
        payload.knowledge_base_id,
    )


@router.get("/{agent_id}/runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    agent_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> AgentRunListResponse:
    return await service.list_runs(user.id, agent_id)


@router.get("/{agent_id}/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    agent_id: UUID,
    run_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> AgentRunResponse:
    return await service.get_run(user.id, agent_id, run_id)


@router.post("/{agent_id}/runs/{run_id}/approve", response_model=AgentRunResponse)
async def approve_agent_run(
    agent_id: UUID,
    run_id: UUID,
    user: UserDependency,
    service: RuntimeServiceDependency,
) -> AgentRunResponse:
    return await service.approve(user.id, agent_id, run_id)


@router.post("/{agent_id}/runs/{run_id}/reject", response_model=AgentRunResponse)
async def reject_agent_run(
    agent_id: UUID,
    run_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> AgentRunResponse:
    return await service.reject(user.id, agent_id, run_id)


@router.post("/{agent_id}/runs/{run_id}/resume", response_model=AgentRunResponse)
async def resume_agent_run(
    agent_id: UUID,
    run_id: UUID,
    user: UserDependency,
    service: RuntimeServiceDependency,
) -> AgentRunResponse:
    return await service.resume(user.id, agent_id, run_id)
