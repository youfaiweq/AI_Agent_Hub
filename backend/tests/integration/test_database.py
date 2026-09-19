"""Integration tests for the running PostgreSQL service."""

import pytest
from sqlalchemy import text

from app.core.database import get_engine, ping_database


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_connection_and_query() -> None:
    await ping_database()

    async with get_engine().connect() as connection:
        result = await connection.execute(text("SELECT current_database()"))
        assert result.scalar_one() == "agenthub"
