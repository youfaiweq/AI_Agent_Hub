"""Authentication endpoints."""

from fastapi import APIRouter, status

from app.core.dependencies import ServiceDependency, UserDependency
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    service: ServiceDependency,
) -> RegisterResponse:
    return await service.register(payload.email, payload.password)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    service: ServiceDependency,
) -> TokenResponse:
    return await service.login(payload.email, payload.password)


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserDependency) -> User:
    return user
