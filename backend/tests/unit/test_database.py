"""Unit tests for database conventions and factories."""

from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.database import get_engine, get_session_factory
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


def test_engine_and_session_factory_are_async() -> None:
    assert isinstance(get_engine(), AsyncEngine)
    factory = get_session_factory()

    assert factory.class_ is AsyncSession
    assert factory.kw["expire_on_commit"] is False


def test_shared_model_conventions_use_uuid_and_utc_timestamps() -> None:
    timestamp = utc_now()

    assert timestamp.tzinfo is UTC
    assert "id" in UUIDPrimaryKeyMixin.__annotations__
    assert "created_at" in TimestampMixin.__annotations__
    assert "updated_at" in TimestampMixin.__annotations__
