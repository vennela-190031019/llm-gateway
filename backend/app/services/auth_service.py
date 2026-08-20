"""Registration and login business logic.

Endpoints translate the exceptions raised here into HTTP responses —
this module has no knowledge of FastAPI.
"""

from __future__ import annotations

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def register(self, email: str, password: str) -> User:
        if await self.user_repository.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)

        is_first_user = await self.user_repository.count() == 0
        role = UserRole.ADMIN if is_first_user else UserRole.USER

        return await self.user_repository.create(
            email=email, hashed_password=hash_password(password), role=role
        )

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(email)
        if not user.is_active:
            raise InactiveUserError(email)
        return user
