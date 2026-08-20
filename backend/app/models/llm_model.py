"""LLM model catalog ORM model — one row per callable model on a provider."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.provider import Provider


class LLMModel(Base):
    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("providers.id"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    input_price_per_1k: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    output_price_per_1k: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    provider: Mapped[Provider] = relationship(back_populates="models")
