"""Chat completion endpoint.

Resolves the request via ChatCompletionService (cache -> routing ->
retry -> fallback), estimates cost, records an LLMRequest audit row
(success or failure), and reports Prometheus metrics + structured logs.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ActiveUser, DbSession
from app.core.logging import get_logger
from app.core.metrics import (
    llm_cost_total,
    llm_errors_total,
    llm_request_latency_seconds,
    llm_requests_total,
    llm_tokens_total,
)
from app.models.llm_request import LLMRequest, LLMRequestStatus
from app.repositories.llm_request_repository import LLMRequestRepository
from app.repositories.model_repository import ModelRepository
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.services.chat_service import AllProvidersExhaustedError, ChatCompletionService
from app.services.cost import CostService, UnknownModelPricingError

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_UNROUTED_LABEL = "none"


def get_chat_service() -> ChatCompletionService:
    return ChatCompletionService()


ChatService = Annotated[ChatCompletionService, Depends(get_chat_service)]


@router.post("/completions", response_model=ChatCompletionResponse)
async def create_completion(
    payload: ChatCompletionRequest,
    session: DbSession,
    current_user: ActiveUser,
    service: ChatService,
) -> ChatCompletionResponse:
    request_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    prompt_chars = sum(len(message.content) for message in payload.messages)

    started = time.monotonic()
    try:
        response = await service.complete(payload, task_type=payload.metadata.task_type)
    except AllProvidersExhaustedError as exc:
        latency_ms = (time.monotonic() - started) * 1000
        await _persist(
            session,
            request_id=request_id,
            trace_id=trace_id,
            user_id=current_user.id,
            model=payload.model,
            provider=None,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=None,
            latency_ms=latency_ms,
            request_status=LLMRequestStatus.ERROR,
            cache_hit=False,
            error=str(exc),
        )

        llm_requests_total.labels(
            model=payload.model, provider=_UNROUTED_LABEL, status=LLMRequestStatus.ERROR
        ).inc()
        llm_request_latency_seconds.labels(model=payload.model, provider=_UNROUTED_LABEL).observe(
            latency_ms / 1000
        )
        llm_errors_total.labels(
            model=payload.model, provider=_UNROUTED_LABEL, error_type=type(exc).__name__
        ).inc()
        logger.warning(
            "chat_completion_failed",
            request_id=str(request_id),
            trace_id=str(trace_id),
            model=payload.model,
            latency_ms=latency_ms,
            status=LLMRequestStatus.ERROR,
            cache_hit=False,
            prompt_chars=prompt_chars,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="All configured providers failed to complete this request.",
        ) from exc

    latency_ms = (time.monotonic() - started) * 1000

    estimated_cost: Decimal | None
    try:
        estimated_cost = await CostService(ModelRepository(session)).estimate_cost(
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
    except UnknownModelPricingError as exc:
        estimated_cost = None
        logger.warning(
            "cost_lookup_failed",
            model=response.model,
            provider=response.provider,
            error=str(exc),
        )

    await _persist(
        session,
        request_id=request_id,
        trace_id=trace_id,
        user_id=current_user.id,
        model=response.model,
        provider=response.provider,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        request_status=LLMRequestStatus.SUCCESS,
        cache_hit=response.cached,
        error=None,
    )

    llm_requests_total.labels(
        model=response.model, provider=response.provider, status=LLMRequestStatus.SUCCESS
    ).inc()
    llm_request_latency_seconds.labels(
        model=response.model, provider=response.provider
    ).observe(latency_ms / 1000)
    llm_tokens_total.labels(
        model=response.model, provider=response.provider, type="input"
    ).inc(response.input_tokens)
    llm_tokens_total.labels(
        model=response.model, provider=response.provider, type="output"
    ).inc(response.output_tokens)
    if estimated_cost is not None:
        llm_cost_total.labels(model=response.model, provider=response.provider).inc(
            float(estimated_cost)
        )

    logger.info(
        "chat_completion_succeeded",
        request_id=str(request_id),
        trace_id=str(trace_id),
        model=response.model,
        provider=response.provider,
        latency_ms=latency_ms,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost=float(estimated_cost) if estimated_cost is not None else None,
        status=LLMRequestStatus.SUCCESS,
        cache_hit=response.cached,
        prompt_chars=prompt_chars,
    )

    return response


async def _persist(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    trace_id: uuid.UUID,
    user_id: uuid.UUID,
    model: str,
    provider: str | None,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: Decimal | None,
    latency_ms: float,
    request_status: LLMRequestStatus,
    cache_hit: bool,
    error: str | None,
) -> None:
    record = LLMRequest(
        request_id=request_id,
        trace_id=trace_id,
        user_id=user_id,
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        status=request_status,
        cache_hit=cache_hit,
        error=error,
    )
    await LLMRequestRepository(session).create(record)
    await session.commit()
