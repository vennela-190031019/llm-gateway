"""Pydantic schemas for the evaluations endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.evaluation import EvaluationRunStatus


class EvaluationDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class EvaluationDatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID
    created_at: datetime


class EvaluationCaseCreate(BaseModel):
    # Sent verbatim as an LLM prompt (and, for expected_output, compared
    # against the model's response) during a run — bound it the same way
    # as a chat message.
    input: str = Field(min_length=1, max_length=50_000)
    expected_output: str | None = Field(default=None, max_length=50_000)


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    input: str
    expected_output: str | None
    created_at: datetime


class EvaluationDatasetDetailRead(EvaluationDatasetRead):
    cases: list[EvaluationCaseRead] = Field(default_factory=list)


class EvaluationRunCreate(BaseModel):
    dataset_id: uuid.UUID
    model: str = Field(max_length=200)
    provider: str = Field(max_length=100)
    metrics: list[Annotated[str, Field(max_length=100)]] = Field(min_length=1, max_length=20)


class EvaluationRunSummary(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    model: str
    provider: str
    status: EvaluationRunStatus
    started_at: datetime
    completed_at: datetime | None
    case_count: int
    average_scores: dict[str, float]


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    actual_output: str
    latency_ms: float
    tokens: int
    cost: Decimal | None
    scores: dict[str, float]
    created_at: datetime
