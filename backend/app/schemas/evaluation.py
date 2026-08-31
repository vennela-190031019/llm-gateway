"""Pydantic schemas for the evaluations endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.evaluation import EvaluationRunStatus


class EvaluationDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class EvaluationDatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID
    created_at: datetime


class EvaluationCaseCreate(BaseModel):
    input: str = Field(min_length=1)
    expected_output: str | None = None


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    input: str
    expected_output: str | None
    created_at: datetime


class EvaluationRunCreate(BaseModel):
    dataset_id: uuid.UUID
    model: str
    provider: str
    metrics: list[str] = Field(min_length=1)


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
