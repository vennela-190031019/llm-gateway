"""LLMRequest data access. No business logic — see app.api.v1.chat and
app.api.v1.requests.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_request import LLMRequest, LLMRequestStatus


@dataclass(frozen=True)
class RequestsAggregate:
    """Raw aggregates over a user's requests — percentages are derived
    from these at the API layer, not here.
    """

    total_requests: int
    success_count: int
    cache_hit_count: int
    total_tokens: int
    total_cost: Decimal
    average_latency_ms: float | None


@dataclass(frozen=True)
class ModelCostAggregate:
    model: str
    total_requests: int
    total_tokens: int
    total_cost: Decimal


class LLMRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, llm_request: LLMRequest) -> LLMRequest:
        self.session.add(llm_request)
        await self.session.flush()
        return llm_request

    async def get_by_request_id(self, request_id: uuid.UUID) -> LLMRequest | None:
        return await self.session.get(LLMRequest, request_id)

    async def get_by_request_id_for_user(
        self, request_id: uuid.UUID, user_id: uuid.UUID
    ) -> LLMRequest | None:
        result = await self.session.execute(
            select(LLMRequest).where(
                LLMRequest.request_id == request_id, LLMRequest.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, *, limit: int = 50) -> Sequence[LLMRequest]:
        result = await self.session.execute(
            select(LLMRequest)
            .where(LLMRequest.user_id == user_id)
            .order_by(LLMRequest.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_aggregate_for_user(self, user_id: uuid.UUID) -> RequestsAggregate:
        """Aggregates over *every* request the user has, not just a page of
        them — computed in SQL so it stays cheap regardless of how many
        requests they've accumulated.
        """
        stmt = select(
            func.count(LLMRequest.request_id),
            func.sum(case((LLMRequest.status == LLMRequestStatus.SUCCESS, 1), else_=0)),
            func.sum(case((LLMRequest.cache_hit.is_(True), 1), else_=0)),
            func.sum(LLMRequest.total_tokens),
            func.sum(LLMRequest.estimated_cost),
            func.avg(LLMRequest.latency_ms),
        ).where(LLMRequest.user_id == user_id)

        total, success_count, cache_hit_count, total_tokens, total_cost, average_latency_ms = (
            await self.session.execute(stmt)
        ).one()

        return RequestsAggregate(
            total_requests=total or 0,
            success_count=success_count or 0,
            cache_hit_count=cache_hit_count or 0,
            total_tokens=total_tokens or 0,
            total_cost=_as_decimal(total_cost),
            average_latency_ms=(
                float(average_latency_ms) if average_latency_ms is not None else None
            ),
        )

    async def get_cost_by_model_for_user(
        self, user_id: uuid.UUID
    ) -> Sequence[ModelCostAggregate]:
        """Per-model totals over *every* request the user has — for an
        accurate cost breakdown, not just a capped/paginated page of
        recent requests (see app.api.v1.requests.list_requests).
        """
        stmt = (
            select(
                LLMRequest.model,
                func.count(LLMRequest.request_id),
                func.sum(LLMRequest.total_tokens),
                func.sum(LLMRequest.estimated_cost),
            )
            .where(LLMRequest.user_id == user_id)
            .group_by(LLMRequest.model)
            .order_by(func.sum(LLMRequest.estimated_cost).desc())
        )

        rows = (await self.session.execute(stmt)).all()
        return [
            ModelCostAggregate(
                model=model,
                total_requests=total_requests or 0,
                total_tokens=total_tokens or 0,
                total_cost=_as_decimal(total_cost),
            )
            for model, total_requests, total_tokens, total_cost in rows
        ]


def _as_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
