"""Agent configuration and run API schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentToolName = Literal["knowledge_search", "calculator", "sql_query", "web_search"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    system_prompt: str | None = Field(default=None, max_length=20000)
    knowledge_base_id: UUID | None = None
    model_name: str = Field(default="qwen-plus", min_length=1, max_length=120)
    max_steps: int = Field(default=5, ge=1, le=20)
    timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    tool_names: list[AgentToolName] = Field(default_factory=lambda: ["knowledge_search", "calculator"])


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    system_prompt: str | None = Field(default=None, max_length=20000)
    knowledge_base_id: UUID | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    max_steps: int | None = Field(default=None, ge=1, le=20)
    timeout_seconds: float | None = Field(default=None, gt=0, le=300)
    tool_names: list[AgentToolName] | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    knowledge_base_id: UUID | None
    name: str
    description: str | None
    system_prompt: str | None
    model_name: str
    max_steps: int
    timeout_seconds: float
    tool_names: list[str]
    created_at: datetime
    updated_at: datetime


class AgentRunCreate(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: UUID | None = None
    knowledge_base_id: UUID | None = None


class ToolCallResponse(BaseModel):
    id: UUID
    call_id: str
    tool_name: str
    status: str
    arguments: dict[str, object] | None
    result: object | None
    error_code: str | None
    error_message: str | None
    duration_ms: float | None
    created_at: datetime
    finished_at: datetime | None


class AgentRunResponse(BaseModel):
    id: UUID
    agent_id: UUID
    conversation_id: UUID | None
    knowledge_base_id: UUID | None
    input_text: str
    status: str
    step_count: int
    max_steps: int
    timeout_seconds: float
    answer: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    tool_calls: list[ToolCallResponse]


class AgentRunListResponse(BaseModel):
    items: list[AgentRunResponse]
