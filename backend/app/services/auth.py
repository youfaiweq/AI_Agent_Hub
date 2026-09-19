"""Authentication service."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterResponse, TokenResponse


class AuthService:
    """Coordinate registration, login, and current-user operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, email: str, password: str) -> RegisterResponse:
        normalized_email = email.strip().lower()
        if await self.users.get_by_email(normalized_email):
            raise AppError("USER_ALREADY_EXISTS", "A user with this email already exists", 409)
        try:
            user = await self.users.create(normalized_email, hash_password(password))
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError("USER_ALREADY_EXISTS", "A user with this email already exists", 409) from exc
        token, expires_in = create_access_token(user.id)
        return RegisterResponse(
            user=user,
            token=TokenResponse(access_token=token, expires_in=expires_in),
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.users.get_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise AppError("INVALID_CREDENTIALS", "Invalid email or password", 401)
        if not user.is_active:
            raise AppError("USER_INACTIVE", "User account is inactive", 403)
        token, expires_in = create_access_token(user.id)
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def get_current_user(self, user_id: UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AppError("USER_NOT_FOUND", "Authenticated user was not found", 401)
        return user
