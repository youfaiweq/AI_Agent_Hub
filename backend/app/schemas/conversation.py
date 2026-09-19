"""Conversation, message, and chat schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CitationResponse(BaseModel):
    citation_id: int
    document_id: str
    filename: str
    chunk_id: str
    page_number: int
    snippet: str


class ConversationCreate(BaseModel):
    knowledge_base_id: UUID
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[CitationResponse]
    created_at: datetime
    updated_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


class ChatResponse(BaseModel):
    conversation: ConversationResponse
    message: MessageResponse
    citations: list[CitationResponse]
