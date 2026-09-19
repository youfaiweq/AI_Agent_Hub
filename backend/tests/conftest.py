"""Shared test isolation fixtures."""

import pytest

from app.core.database import get_engine, get_session_factory


@pytest.fixture(autouse=True)
def clear_database_caches():
    """Avoid reusing async SQLAlchemy factories across pytest event loops."""

    get_session_factory.cache_clear()
    get_engine.cache_clear()
    yield
    get_session_factory.cache_clear()
    get_engine.cache_clear()
