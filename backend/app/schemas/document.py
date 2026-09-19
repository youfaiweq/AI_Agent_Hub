"""Document request and response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentStatusValue = Literal["uploaded", "processing", "completed", "failed"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    status: DocumentStatusValue
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
