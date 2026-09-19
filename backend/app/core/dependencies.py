"""Reusable FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.integrations.minio import MinioAdapter
from app.models.user import User
from app.services.auth import AuthService

bearer_scheme = HTTPBearer(auto_error=False)
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


def get_auth_service(session: SessionDependency) -> AuthService:
    return AuthService(session)


ServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
CredentialsDependency = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


async def get_current_user(
    credentials: CredentialsDependency,
    service: ServiceDependency,
) -> User:
    if credentials is None:
        raise AppError("AUTHENTICATION_REQUIRED", "Authentication required", 401)
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise AppError("INVALID_TOKEN", "Invalid or expired access token", 401) from None
    return await service.get_current_user(user_id)


UserDependency = Annotated[User, Depends(get_current_user)]


async def get_minio_adapter() -> AsyncIterator[MinioAdapter]:
    async with MinioAdapter() as adapter:
        yield adapter


StorageDependency = Annotated[MinioAdapter, Depends(get_minio_adapter)]
