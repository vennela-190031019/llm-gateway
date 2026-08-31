"""ORM models.

All models are imported here so a single `import app.models` registers
the full schema on `Base.metadata` — required for Alembic autogenerate.
"""

from __future__ import annotations

from app.models.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
)
from app.models.llm_model import LLMModel
from app.models.llm_request import LLMRequest, LLMRequestStatus
from app.models.prompt import PromptTemplate, PromptVersion
from app.models.provider import Provider
from app.models.user import User, UserRole

__all__ = [
    "EvaluationCase",
    "EvaluationDataset",
    "EvaluationResult",
    "EvaluationRun",
    "EvaluationRunStatus",
    "LLMModel",
    "LLMRequest",
    "LLMRequestStatus",
    "PromptTemplate",
    "PromptVersion",
    "Provider",
    "User",
    "UserRole",
]
