"""Models endpoint — lists active models in the catalog.

Gated by `require_user` to demonstrate the auth guard; any authenticated,
active user (not just admins) can browse the catalog.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.dependencies import ActiveUser, DbSession
from app.core.rate_limit import DEFAULT_RATE_LIMIT, limiter
from app.repositories.model_repository import ModelRepository
from app.schemas.model import ModelRead

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelRead])
@limiter.limit(DEFAULT_RATE_LIMIT)
async def list_models(
    request: Request, session: DbSession, _current_user: ActiveUser
) -> list[ModelRead]:
    models = await ModelRepository(session).list_active()
    return [
        ModelRead(
            id=model.id,
            name=model.name,
            provider_name=model.provider.name,
            tier=model.tier,
            input_price_per_1k=model.input_price_per_1k,
            output_price_per_1k=model.output_price_per_1k,
            is_active=model.is_active,
        )
        for model in models
    ]
