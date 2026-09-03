"""Request-history endpoints: list/detail/summary over a user's own
LLMRequest audit rows (see app.api.v1.chat, which writes them).

Scoped to the current user, not global — LLMRequest has no notion of
"team" or "admin visibility" yet, and every other per-workspace resource
in this API (prompts, evaluations) is likewise scoped to its owner. The
detail endpoint 404s (not 403s) for another user's request id, so it
doesn't leak which ids exist.

Route order matters here: /summary and /cost-by-model must be declared
before /{request_id} — otherwise FastAPI would try to parse them as a
UUID path param and 422 before ever reaching the intended handler.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import ActiveUser, DbSession
from app.models.llm_request import LLMRequest
from app.repositories.llm_request_repository import LLMRequestRepository
from app.schemas.llm_request import LLMRequestRead, ModelCostRead, RequestsSummaryRead

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("", response_model=list[LLMRequestRead])
async def list_requests(
    session: DbSession,
    current_user: ActiveUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[LLMRequest]:
    return list(await LLMRequestRepository(session).list_for_user(current_user.id, limit=limit))


@router.get("/summary", response_model=RequestsSummaryRead)
async def get_requests_summary(
    session: DbSession, current_user: ActiveUser
) -> RequestsSummaryRead:
    aggregate = await LLMRequestRepository(session).get_aggregate_for_user(current_user.id)

    if aggregate.total_requests == 0:
        return RequestsSummaryRead(
            total_requests=0,
            success_rate=None,
            average_latency_ms=None,
            total_tokens=0,
            total_cost=aggregate.total_cost,
            cache_hit_rate=None,
        )

    return RequestsSummaryRead(
        total_requests=aggregate.total_requests,
        success_rate=(aggregate.success_count / aggregate.total_requests) * 100,
        average_latency_ms=aggregate.average_latency_ms,
        total_tokens=aggregate.total_tokens,
        total_cost=aggregate.total_cost,
        cache_hit_rate=(aggregate.cache_hit_count / aggregate.total_requests) * 100,
    )


@router.get("/cost-by-model", response_model=list[ModelCostRead])
async def get_cost_by_model(session: DbSession, current_user: ActiveUser) -> list[ModelCostRead]:
    aggregates = await LLMRequestRepository(session).get_cost_by_model_for_user(current_user.id)
    return [
        ModelCostRead(
            model=aggregate.model,
            total_requests=aggregate.total_requests,
            total_tokens=aggregate.total_tokens,
            total_cost=aggregate.total_cost,
        )
        for aggregate in aggregates
    ]


@router.get("/{request_id}", response_model=LLMRequestRead)
async def get_request(
    request_id: uuid.UUID, session: DbSession, current_user: ActiveUser
) -> LLMRequest:
    request = await LLMRequestRepository(session).get_by_request_id_for_user(
        request_id, current_user.id
    )
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no request with id {request_id}"
        )
    return request
