"""Prompt template endpoints.

Any authenticated, active user can create and manage prompt templates
(gated by `require_user`, not `require_admin`): prompts are a
per-workspace authoring tool similar to saved queries, not system-wide
configuration like the model catalog — restricting creation to admins
would make the feature unusable for the regular users it's meant for.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request, status

from app.core.dependencies import ActiveUser, DbSession
from app.models.prompt import PromptTemplate, PromptVersion
from app.repositories.prompt_repository import PromptRepository
from app.schemas.prompt import (
    PromptRenderRequest,
    PromptRenderResponse,
    PromptTemplateCreate,
    PromptTemplateDetailRead,
    PromptTemplateRead,
    PromptVersionCreate,
    PromptVersionRead,
)
from app.services.prompt_service import (
    MissingPromptVariableError,
    PromptRenderError,
    PromptService,
    PromptTemplateAlreadyExistsError,
    PromptTemplateNotFoundError,
    PromptVersionNotFoundError,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post("", response_model=PromptTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: PromptTemplateCreate, session: DbSession, current_user: ActiveUser
) -> PromptTemplate:
    service = PromptService(PromptRepository(session))
    try:
        template = await service.create_template(
            name=payload.name, description=payload.description, owner_id=current_user.id
        )
    except PromptTemplateAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await session.commit()
    return template


@router.post(
    "/{name}/versions", response_model=PromptVersionRead, status_code=status.HTTP_201_CREATED
)
async def create_version(
    name: str, payload: PromptVersionCreate, session: DbSession, _current_user: ActiveUser
) -> PromptVersion:
    service = PromptService(PromptRepository(session))
    try:
        version = await service.create_version(
            template_name=name,
            template_text=payload.template_text,
            variables=payload.variables,
            model=payload.model,
            temperature=payload.temperature,
        )
    except PromptTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return version


@router.get("", response_model=list[PromptTemplateRead])
async def list_templates(session: DbSession, _current_user: ActiveUser) -> list[PromptTemplate]:
    return list(await PromptRepository(session).list_templates())


@router.get("/{name}", response_model=PromptTemplateDetailRead)
async def get_template(
    name: str, session: DbSession, _current_user: ActiveUser
) -> PromptTemplate:
    template = await PromptRepository(session).get_template_by_name(name)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no prompt template named {name!r}"
        )
    return template


@router.get("/{name}/render", response_model=PromptRenderResponse)
async def render_template(
    name: str,
    request: Request,
    session: DbSession,
    _current_user: ActiveUser,
    version: int | None = None,
    body: Annotated[PromptRenderRequest | None, Body()] = None,
) -> PromptRenderResponse:
    variables = {
        key: value for key, value in request.query_params.items() if key != "version"
    }
    if body is not None:
        variables.update(body.variables)
        if body.version is not None:
            version = body.version

    service = PromptService(PromptRepository(session))
    try:
        rendered = await service.render(template_name=name, variables=variables, version=version)
    except (PromptTemplateNotFoundError, PromptVersionNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (MissingPromptVariableError, PromptRenderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return PromptRenderResponse(
        content=rendered.content,
        model=rendered.model,
        temperature=rendered.temperature,
        version=rendered.version,
    )


@router.patch("/{name}/versions/{version}/activate", response_model=PromptVersionRead)
async def activate_version(
    name: str, version: int, session: DbSession, _current_user: ActiveUser
) -> PromptVersion:
    service = PromptService(PromptRepository(session))
    try:
        activated = await service.set_active_version(template_name=name, version=version)
    except (PromptTemplateNotFoundError, PromptVersionNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return activated
