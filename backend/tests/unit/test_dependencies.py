from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.dependencies import require_admin, require_user
from app.models.user import User, UserRole


def _user(*, role: UserRole = UserRole.USER, is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="guarded@example.com",
        hashed_password="irrelevant",
        role=role,
        is_active=is_active,
    )


async def test_require_user_allows_active_user() -> None:
    user = _user(is_active=True)
    assert await require_user(user) is user


async def test_require_user_rejects_inactive_user() -> None:
    user = _user(is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        await require_user(user)
    assert exc_info.value.status_code == 403


async def test_require_admin_allows_admin() -> None:
    admin = _user(role=UserRole.ADMIN)
    assert await require_admin(admin) is admin


async def test_require_admin_rejects_plain_user() -> None:
    user = _user(role=UserRole.USER)
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(user)
    assert exc_info.value.status_code == 403
