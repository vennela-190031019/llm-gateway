"""LLMRequest data access. No business logic — see app.api.v1.chat."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_request import LLMRequest


class LLMRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, llm_request: LLMRequest) -> LLMRequest:
        self.session.add(llm_request)
        await self.session.flush()
        return llm_request

    async def get_by_request_id(self, request_id: uuid.UUID) -> LLMRequest | None:
        return await self.session.get(LLMRequest, request_id)

    async def list_for_user(self, user_id: uuid.UUID, *, limit: int = 50) -> Sequence[LLMRequest]:
        result = await self.session.execute(
            select(LLMRequest)
            .where(LLMRequest.user_id == user_id)
            .order_by(LLMRequest.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
