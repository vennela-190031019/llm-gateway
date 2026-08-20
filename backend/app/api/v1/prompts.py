"""Prompts endpoints — implemented in a later phase.

Router is registered in app.main so the full API surface and OpenAPI
grouping is visible from Phase 1 onward, even before handlers exist.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/prompts", tags=["prompts"])
