from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt_repository import PromptRepository
from app.services.prompt_service import (
    MissingPromptVariableError,
    PromptService,
    PromptTemplateAlreadyExistsError,
    PromptTemplateNotFoundError,
    PromptVersionNotFoundError,
)


def _service(db_session: AsyncSession) -> PromptService:
    return PromptService(PromptRepository(db_session))


async def _make_template(service: PromptService, name: str = "greeting") -> None:
    await service.create_template(name=name, description=None, owner_id=uuid.uuid4())


async def test_create_template(db_session: AsyncSession) -> None:
    service = _service(db_session)
    owner_id = uuid.uuid4()

    template = await service.create_template(
        name="customer-support", description="Support replies", owner_id=owner_id
    )

    assert template.name == "customer-support"
    assert template.description == "Support replies"
    assert template.owner_id == owner_id


async def test_create_template_rejects_duplicate_name(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service, "dupe")

    with pytest.raises(PromptTemplateAlreadyExistsError):
        await _make_template(service, "dupe")


async def test_create_version_requires_existing_template(db_session: AsyncSession) -> None:
    service = _service(db_session)

    with pytest.raises(PromptTemplateNotFoundError):
        await service.create_version(
            template_name="ghost",
            template_text="hi {name}",
            variables=["name"],
            model="gpt-4o-mini",
            temperature=0.5,
        )


async def test_create_version_auto_increments(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service)

    v1 = await service.create_version(
        template_name="greeting",
        template_text="Hi {name}",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.5,
    )
    v2 = await service.create_version(
        template_name="greeting",
        template_text="Hello {name}!",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.7,
    )

    assert v1.version == 1
    assert v2.version == 2


async def test_first_version_is_active_by_default_and_later_ones_are_not(
    db_session: AsyncSession,
) -> None:
    service = _service(db_session)
    await _make_template(service)

    v1 = await service.create_version(
        template_name="greeting",
        template_text="Hi {name}",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.5,
    )
    v2 = await service.create_version(
        template_name="greeting",
        template_text="Hello {name}!",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.7,
    )

    assert v1.is_active is True
    assert v2.is_active is False


async def test_render_with_all_variables_present(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service)
    await service.create_version(
        template_name="greeting",
        template_text="Hi {name}, welcome to {place}!",
        variables=["name", "place"],
        model="gpt-4o-mini",
        temperature=0.5,
    )

    rendered = await service.render(
        template_name="greeting", variables={"name": "Ada", "place": "the lab"}
    )

    assert rendered.content == "Hi Ada, welcome to the lab!"
    assert rendered.model == "gpt-4o-mini"
    assert rendered.temperature == 0.5
    assert rendered.version == 1


async def test_render_with_missing_variables_raises(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service)
    await service.create_version(
        template_name="greeting",
        template_text="Hi {name}, welcome to {place}!",
        variables=["name", "place"],
        model="gpt-4o-mini",
        temperature=0.5,
    )

    with pytest.raises(MissingPromptVariableError) as exc_info:
        await service.render(template_name="greeting", variables={"name": "Ada"})

    assert exc_info.value.missing == ["place"]


async def test_render_without_any_active_version_raises(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service, "empty")

    with pytest.raises(PromptVersionNotFoundError):
        await service.render(template_name="empty", variables={})


async def test_render_unknown_template_raises(db_session: AsyncSession) -> None:
    service = _service(db_session)

    with pytest.raises(PromptTemplateNotFoundError):
        await service.render(template_name="ghost", variables={})


async def test_render_specific_version_vs_latest_active(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service)
    await service.create_version(
        template_name="greeting",
        template_text="Hi {name}",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.5,
    )
    await service.create_version(
        template_name="greeting",
        template_text="Hello there, {name}!",
        variables=["name"],
        model="gpt-4o",
        temperature=0.9,
    )

    rendered_v1 = await service.render(
        template_name="greeting", variables={"name": "Ada"}, version=1
    )
    rendered_latest_active = await service.render(
        template_name="greeting", variables={"name": "Ada"}
    )

    assert rendered_v1.content == "Hi Ada"
    assert rendered_v1.version == 1
    # v2 was created but never activated, so "latest active" still serves v1.
    assert rendered_latest_active.version == 1


async def test_render_missing_version_raises(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service)
    await service.create_version(
        template_name="greeting",
        template_text="Hi {name}",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.5,
    )

    with pytest.raises(PromptVersionNotFoundError):
        await service.render(template_name="greeting", variables={"name": "Ada"}, version=99)


async def test_activating_a_different_version_changes_latest_active(
    db_session: AsyncSession,
) -> None:
    service = _service(db_session)
    await _make_template(service)
    await service.create_version(
        template_name="greeting",
        template_text="Hi {name}",
        variables=["name"],
        model="gpt-4o-mini",
        temperature=0.5,
    )
    await service.create_version(
        template_name="greeting",
        template_text="Hello there, {name}!",
        variables=["name"],
        model="gpt-4o",
        temperature=0.9,
    )

    activated = await service.set_active_version(template_name="greeting", version=2)
    rendered = await service.render(template_name="greeting", variables={"name": "Ada"})

    assert activated.is_active is True
    assert rendered.version == 2
    assert rendered.content == "Hello there, Ada!"


async def test_activate_unknown_version_raises(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_template(service)

    with pytest.raises(PromptVersionNotFoundError):
        await service.set_active_version(template_name="greeting", version=1)


async def test_activate_version_on_unknown_template_raises(db_session: AsyncSession) -> None:
    service = _service(db_session)

    with pytest.raises(PromptTemplateNotFoundError):
        await service.set_active_version(template_name="ghost", version=1)
