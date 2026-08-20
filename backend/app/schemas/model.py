"""Pydantic schemas for the models endpoint."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel


class ModelRead(BaseModel):
    id: uuid.UUID
    name: str
    provider_name: str
    tier: str
    input_price_per_1k: Decimal
    output_price_per_1k: Decimal
    is_active: bool
