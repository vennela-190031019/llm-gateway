"""Prompt template/version data access. No business logic — see
app.services.prompt_service.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.prompt import PromptTemplate, PromptVersion


class PromptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # Templates

    async def create_template(self, template: PromptTemplate) -> PromptTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_template_by_name(self, name: str) -> PromptTemplate | None:
        result = await self.session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.name == name)
            .options(selectinload(PromptTemplate.versions))
        )
        return result.scalar_one_or_none()

    async def list_templates(self) -> Sequence[PromptTemplate]:
        result = await self.session.execute(select(PromptTemplate).order_by(PromptTemplate.name))
        return result.scalars().all()

    # Versions

    async def create_version(self, version: PromptVersion) -> PromptVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_max_version_number(self, prompt_template_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.max(PromptVersion.version)).where(
                PromptVersion.prompt_template_id == prompt_template_id
            )
        )
        return result.scalar_one() or 0

    async def get_version(
        self, prompt_template_id: uuid.UUID, version: int
    ) -> PromptVersion | None:
        result = await self.session.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_template_id == prompt_template_id,
                PromptVersion.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_version_by_template_name(self, name: str) -> PromptVersion | None:
        result = await self.session.execute(
            select(PromptVersion)
            .join(PromptTemplate, PromptVersion.prompt_template_id == PromptTemplate.id)
            .where(PromptTemplate.name == name, PromptVersion.is_active.is_(True))
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def deactivate_all_versions(self, prompt_template_id: uuid.UUID) -> None:
        await self.session.execute(
            update(PromptVersion)
            .where(PromptVersion.prompt_template_id == prompt_template_id)
            .values(is_active=False)
        )
