"""Conversation and chat endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import (
    EmbeddingDependency,
    ObservabilityDependency,
    SessionDependency,
    UserDependency,
    VectorStoreDependency,
)
from app.rag.llms import LLMProvider
from app.rag.retrievers.dense import DenseRetriever
from app.schemas.conversation import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    MessageListResponse,
)
from app.services.chat import ChatService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_llm_provider() -> LLMProvider:
    from app.core.config import get_settings
    from app.rag.llms.openai_compatible import OpenAICompatibleLLMProvider

    settings = get_settings()
    if settings.llm_provider != "openai_compatible":
        raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")
    return OpenAICompatibleLLMProvider(settings=settings)


LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]


def get_chat_service(
    session: SessionDependency,
    embedder: EmbeddingDependency,
    vector_store: VectorStoreDependency,
    llm: LLMDependency,
    observability: ObservabilityDependency,
) -> ChatService:
    return ChatService(session, DenseRetriever(embedder, vector_store), llm, observability)


ServiceDependency = Annotated[ChatService, Depends(get_chat_service)]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    user: UserDependency,
    service: ServiceDependency,
) -> ConversationResponse:
    return await service.create_conversation(user.id, payload)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    user: UserDependency,
    service: ServiceDependency,
) -> list[ConversationResponse]:
    return await service.list_conversations(user.id)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> ConversationResponse:
    conversation = await service.get_conversation(user.id, conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> MessageListResponse:
    return await service.list_messages(user.id, conversation_id)


@router.post("/{conversation_id}/chat", response_model=ChatResponse)
async def chat(
    conversation_id: UUID,
    payload: ChatRequest,
    user: UserDependency,
    service: ServiceDependency,
) -> ChatResponse:
    return await service.chat(user.id, conversation_id, payload.message)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> Response:
    await service.delete_conversation(user.id, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
