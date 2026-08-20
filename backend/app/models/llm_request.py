"""Per-request observability record: tokens, cost, latency, and outcome.

One row per call to POST /chat/completions, success or failure — see
app.repositories.llm_request_repository and app.api.v1.chat.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class LLMRequestStatus(enum.StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class LLMRequest(Base):
    __tablename__ = "llm_requests"

    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )

    model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[LLMRequestStatus] = mapped_column(
        Enum(LLMRequestStatus, name="llm_request_status"), nullable=False
    )
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
