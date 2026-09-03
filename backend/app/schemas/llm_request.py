"""Pydantic schemas for the requests endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.llm_request import LLMRequestStatus


class LLMRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    trace_id: uuid.UUID
    user_id: uuid.UUID
    model: str
    provider: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal | None
    latency_ms: float
    status: LLMRequestStatus
    cache_hit: bool
    error: str | None
    created_at: datetime


class RequestsSummaryRead(BaseModel):
    """Aggregated across *all* of the current user's requests, not just a
    capped/paginated page of them — see
    LLMRequestRepository.get_summary_for_user.
    """

    total_requests: int
    success_rate: float | None
    average_latency_ms: float | None
    total_tokens: int
    total_cost: Decimal
    cache_hit_rate: float | None


class ModelCostRead(BaseModel):
    """One row of LLMRequestRepository.get_cost_by_model_for_user — also
    aggregated across *all* of the user's requests, not a capped page.
    """

    model: str
    total_requests: int
    total_tokens: int
    total_cost: Decimal
