"""Prompt template business logic: versioning and safe rendering.

Endpoints translate the exceptions raised here into HTTP responses —
this module has no knowledge of FastAPI.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.prompt import PromptTemplate, PromptVersion
from app.repositories.prompt_repository import PromptRepository


class PromptTemplateAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"a prompt template named {name!r} already exists")


class PromptTemplateNotFoundError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"no prompt template named {name!r}")


class PromptVersionNotFoundError(Exception):
    def __init__(self, template_name: str, version: int | None) -> None:
        self.template_name = template_name
        self.version = version
        message = (
            f"template {template_name!r} has no active version"
            if version is None
            else f"template {template_name!r} has no version {version}"
        )
        super().__init__(message)


class MissingPromptVariableError(Exception):
    def __init__(self, template_name: str, missing: list[str]) -> None:
        self.template_name = template_name
        self.missing = missing
        super().__init__(
            f"template {template_name!r} is missing required variables: {', '.join(missing)}"
        )


class PromptRenderError(Exception):
    def __init__(self, template_name: str, detail: str) -> None:
        self.template_name = template_name
        super().__init__(f"failed to render template {template_name!r}: {detail}")


@dataclass(frozen=True)
class RenderedPrompt:
    content: str
    model: str
    temperature: float
    version: int


class PromptService:
    def __init__(self, repository: PromptRepository) -> None:
        self._repository = repository

    async def create_template(
        self, *, name: str, description: str | None, owner_id: uuid.UUID
    ) -> PromptTemplate:
        if await self._repository.get_template_by_name(name) is not None:
            raise PromptTemplateAlreadyExistsError(name)

        template = PromptTemplate(name=name, description=description, owner_id=owner_id)
        return await self._repository.create_template(template)

    async def create_version(
        self,
        *,
        template_name: str,
        template_text: str,
        variables: list[str],
        model: str,
        temperature: float,
    ) -> PromptVersion:
        template = await self._repository.get_template_by_name(template_name)
        if template is None:
            raise PromptTemplateNotFoundError(template_name)

        next_version = await self._repository.get_max_version_number(template.id) + 1
        version = PromptVersion(
            prompt_template_id=template.id,
            version=next_version,
            template_text=template_text,
            variables=variables,
            model=model,
            temperature=temperature,
            # The first version of a template is active by default so
            # `render()` has something to serve without an extra step.
            is_active=next_version == 1,
        )
        return await self._repository.create_version(version)

    async def set_active_version(self, *, template_name: str, version: int) -> PromptVersion:
        template = await self._repository.get_template_by_name(template_name)
        if template is None:
            raise PromptTemplateNotFoundError(template_name)

        target = await self._repository.get_version(template.id, version)
        if target is None:
            raise PromptVersionNotFoundError(template_name, version)

        await self._repository.deactivate_all_versions(template.id)
        target.is_active = True
        return target

    async def render(
        self,
        *,
        template_name: str,
        variables: dict[str, str],
        version: int | None = None,
    ) -> RenderedPrompt:
        template = await self._repository.get_template_by_name(template_name)
        if template is None:
            raise PromptTemplateNotFoundError(template_name)

        if version is not None:
            prompt_version = await self._repository.get_version(template.id, version)
            if prompt_version is None:
                raise PromptVersionNotFoundError(template_name, version)
        else:
            prompt_version = await self._repository.get_active_version_by_template_name(
                template_name
            )
            if prompt_version is None:
                raise PromptVersionNotFoundError(template_name, None)

        missing = [name for name in prompt_version.variables if name not in variables]
        if missing:
            raise MissingPromptVariableError(template_name, missing)

        try:
            content = prompt_version.template_text.format(**variables)
        except (KeyError, IndexError) as exc:
            raise PromptRenderError(template_name, f"unresolved placeholder {exc}") from exc

        return RenderedPrompt(
            content=content,
            model=prompt_version.model,
            temperature=prompt_version.temperature,
            version=prompt_version.version,
        )
