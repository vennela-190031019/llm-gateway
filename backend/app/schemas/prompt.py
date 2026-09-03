"""Pydantic schemas for the prompts endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

_RenderVariableName = Annotated[str, Field(max_length=100)]
_RenderVariableValue = Annotated[str, Field(max_length=10_000)]


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class PromptVersionCreate(BaseModel):
    template_text: str = Field(min_length=1, max_length=50_000)
    variables: list[Annotated[str, Field(max_length=100)]] = Field(
        default_factory=list, max_length=50
    )
    model: str = Field(max_length=200)
    temperature: float = Field(default=1.0, ge=0, le=2)


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

    variables: dict[_RenderVariableName, _RenderVariableValue] = Field(
        default_factory=dict, max_length=50
    )
    version: int | None = Field(default=None, ge=1)


class PromptRenderResponse(BaseModel):
    content: str
    model: str
    temperature: float
    version: int
