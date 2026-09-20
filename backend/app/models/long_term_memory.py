"""Explicit long-term memory persistence model."""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryType(StrEnum):
    """Supported categories for user-approved memories."""

    FACT = "fact"
    PREFERENCE = "preference"
    INSTRUCTION = "instruction"
    METRIC = "metric"


class MemorySource(StrEnum):
    """Sources that satisfy the explicit-save requirement."""

    EXPLICIT_USER = "explicit_user"
    USER_CONFIRMED = "user_confirmed"


class LongTermMemory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-owned memory saved explicitly or after user confirmation."""

    __tablename__ = "long_term_memories"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
