"""LLM model catalog data access. No business logic."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.llm_model import LLMModel


class ModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> Sequence[LLMModel]:
        result = await self.session.execute(
            select(LLMModel)
            .where(LLMModel.is_active.is_(True))
            .options(selectinload(LLMModel.provider))
        )
        return result.scalars().all()
