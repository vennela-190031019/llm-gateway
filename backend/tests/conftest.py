"""Shared test fixtures.

Tests run against an in-memory SQLite database via aiosqlite instead of
Postgres, so the suite runs without Docker. A StaticPool keeps a single
connection alive for the whole fixture so the in-memory schema isn't
dropped between uses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers models on Base.metadata
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _disable_rate_limiting() -> Iterator[None]:
    """Off by default for the whole suite: httpx's ASGITransport gives
    every test client the same "IP", and the Limiter is one process-wide
    instance, so its hit counters would otherwise accumulate across
    unrelated tests and start rejecting auth calls well before the suite
    finishes. Tests that specifically exercise rate limiting (see
    tests/api/test_rate_limiting.py) re-enable it for just themselves.
    """
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # raise_app_exceptions=False: Starlette's exception-handling machinery
    # sends a response for an unhandled exception (see app.main's global
    # handler) but then *also* re-raises it, by design, so a real ASGI
    # server can log it — real servers (uvicorn, verified manually)
    # tolerate that and the client still gets the clean response.
    # ASGITransport's default (True) instead surfaces that re-raise as a
    # hard failure of the test request itself, which would make it
    # impossible to test the global exception handler's actual contract.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
