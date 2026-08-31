"""Pydantic schemas for the prompts endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class PromptVersionCreate(BaseModel):
    template_text: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    model: str
    temperature: float = 1.0


class PromptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    template_text: str
    variables: list[str]
    model: str
    temperature: float
    is_active: bool
    created_at: datetime


class PromptTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID
    created_at: datetime


class PromptTemplateDetailRead(PromptTemplateRead):
    versions: list[PromptVersionRead] = Field(default_factory=list)


class PromptRenderRequest(BaseModel):
    """Optional JSON body for GET /prompts/{name}/render.

    Query parameters work too (see the endpoint) — this is for callers
    who'd rather send variables as a body, e.g. many/complex values.
    """

    variables: dict[str, str] = Field(default_factory=dict)
    version: int | None = None


class PromptRenderResponse(BaseModel):
    content: str
    model: str
    temperature: float
    version: int
