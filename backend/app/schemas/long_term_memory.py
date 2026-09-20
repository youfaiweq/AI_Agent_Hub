"""Long-term memory request and response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MemoryTypeValue = Literal["fact", "preference", "instruction", "metric"]
MemorySourceValue = Literal["explicit_user", "user_confirmed"]


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    memory_type: MemoryTypeValue = "fact"
    source: MemorySourceValue = "explicit_user"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    memory_type: MemoryTypeValue | None = None
    source: MemorySourceValue | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content: str
    memory_type: MemoryTypeValue
    source: MemorySourceValue
    confidence: float
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    total: int
    page: int
    page_size: int


class MemoryExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized


class MemoryCandidate(BaseModel):
    content: str
    memory_type: MemoryTypeValue
    source: MemorySourceValue
    confidence: float


class MemoryExtractResponse(BaseModel):
    candidates: list[MemoryCandidate]
    requires_confirmation: bool
