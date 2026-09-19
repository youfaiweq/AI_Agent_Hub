"""Integration tests for the authentication flow."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import dispose_engine, get_db_session, get_engine, get_session_factory
from app.main import app
from app.models.user import User


def test_register_login_and_current_user() -> None:
    email = f"auth-{uuid4()}@example.com"

    async def override_db_session():
        async with get_session_factory()() as session:
            yield session

    async def cleanup() -> None:
        async with get_session_factory()() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.execute(delete(User).where(User.id == user.id))
                await session.commit()
        await dispose_engine()
        get_engine.cache_clear()

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as client:
            registered = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "correct-horse-battery"},
            )
            assert registered.status_code == 201
            token = registered.json()["token"]["access_token"]
            assert registered.json()["user"]["email"] == email

            duplicate = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "correct-horse-battery"},
            )
            assert duplicate.status_code == 409

            invalid_login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
            )
            assert invalid_login.status_code == 401

            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "correct-horse-battery"},
            )
            assert login.status_code == 200

            me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200
            assert me.json()["email"] == email
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(cleanup())
