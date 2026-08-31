"""EvaluationService tests, run against the real ModelRouter/FallbackExecutor
(same pattern as test_chat_service.py) with the provider registry
monkeypatched to fake providers — no real LLM calls.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import wait_none

from app.models.evaluation import EvaluationRunStatus
from app.models.llm_model import LLMModel
from app.models.provider import Provider
from app.providers.exceptions import ProviderTimeoutError
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.chat_service import ChatCompletionService
from app.services.cost import CostService
from app.services.evaluation_service import (
    EvaluationDatasetAlreadyExistsError,
    EvaluationDatasetNotFoundError,
    EvaluationService,
    aggregate_scores,
)
from app.services.evaluators import relevance as relevance_module
from app.services.evaluators.registry import UnknownEvaluatorError
from app.services.fallback import FallbackExecutor
from app.services.router import ModelRouter

from .fakes import FakeProvider, make_fake_cache_service, make_response


def _service(
    db_session: AsyncSession, *, cost_service: CostService | None = None
) -> EvaluationService:
    chat_service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    return EvaluationService(
        EvaluationRepository(db_session), chat_service=chat_service, cost_service=cost_service
    )


def _patch_providers(monkeypatch: pytest.MonkeyPatch, providers: dict[str, FakeProvider]) -> None:
    from app.services import fallback as fallback_module

    monkeypatch.setattr(fallback_module, "get_provider", lambda name: providers[name])


async def _seed_pricing(db_session: AsyncSession) -> None:
    provider = Provider(name="openai", base_url="https://api.openai.com/v1", is_active=True)
    db_session.add(provider)
    await db_session.flush()
    db_session.add(
        LLMModel(
            name="gpt-4o-mini",
            provider_id=provider.id,
            tier="standard",
            input_price_per_1k="0.150000",
            output_price_per_1k="0.600000",
            is_active=True,
        )
    )
    await db_session.commit()


async def _make_dataset(
    service: EvaluationService, name: str = "geography"
) -> uuid.UUID:
    dataset = await service.create_dataset(name=name, description=None, owner_id=uuid.uuid4())
    return dataset.id


async def test_create_dataset(db_session: AsyncSession) -> None:
    service = _service(db_session)
    owner_id = uuid.uuid4()

    dataset = await service.create_dataset(
        name="geography", description="Capital cities", owner_id=owner_id
    )

    assert dataset.name == "geography"
    assert dataset.description == "Capital cities"
    assert dataset.owner_id == owner_id


async def test_create_dataset_rejects_duplicate_name(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await _make_dataset(service, "dupe")

    with pytest.raises(EvaluationDatasetAlreadyExistsError):
        await _make_dataset(service, "dupe")


async def test_add_case_requires_existing_dataset(db_session: AsyncSession) -> None:
    service = _service(db_session)

    with pytest.raises(EvaluationDatasetNotFoundError):
        await service.add_case(dataset_id=uuid.uuid4(), input="hi", expected_output=None)


async def test_add_case(db_session: AsyncSession) -> None:
    service = _service(db_session)
    dataset_id = await _make_dataset(service)

    case = await service.add_case(
        dataset_id=dataset_id, input="What is the capital of France?", expected_output="Paris"
    )

    assert case.dataset_id == dataset_id
    assert case.input == "What is the capital of France?"
    assert case.expected_output == "Paris"


async def test_run_evaluation_requires_existing_dataset(db_session: AsyncSession) -> None:
    service = _service(db_session)

    with pytest.raises(EvaluationDatasetNotFoundError):
        await service.run_evaluation(
            dataset_id=uuid.uuid4(), model="gpt-4o-mini", provider="openai", metrics=["exact_match"]
        )


async def test_run_evaluation_rejects_unknown_metric_without_creating_run(
    db_session: AsyncSession,
) -> None:
    service = _service(db_session)
    dataset_id = await _make_dataset(service)
    await service.add_case(dataset_id=dataset_id, input="hi", expected_output="hi")

    with pytest.raises(UnknownEvaluatorError):
        await service.run_evaluation(
            dataset_id=dataset_id, model="gpt-4o-mini", provider="openai", metrics=["not-a-metric"]
        )


async def test_run_evaluation_persists_results_and_completes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_pricing(db_session)
    fake_provider = FakeProvider(
        "openai",
        [make_response(provider="openai", model="gpt-4o-mini", content="Paris")],
    )
    _patch_providers(monkeypatch, {"openai": fake_provider})

    service = _service(db_session)
    dataset_id = await _make_dataset(service)
    await service.add_case(
        dataset_id=dataset_id, input="What is the capital of France?", expected_output="Paris"
    )

    run = await service.run_evaluation(
        dataset_id=dataset_id, model="gpt-4o-mini", provider="openai", metrics=["exact_match"]
    )
    await db_session.commit()

    assert run.status == EvaluationRunStatus.COMPLETED
    assert run.completed_at is not None
    assert run.provider == "openai"
    assert len(run.results) == 1
    result = run.results[0]
    assert result.actual_output == "Paris"
    assert result.scores == {"exact_match": 1.0}
    assert result.tokens == 2
    assert result.cost is not None


async def test_run_evaluation_without_pricing_records_null_cost(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="Paris")]
    )
    _patch_providers(monkeypatch, {"openai": fake_provider})

    service = _service(db_session)
    dataset_id = await _make_dataset(service)
    await service.add_case(
        dataset_id=dataset_id, input="What is the capital of France?", expected_output="Paris"
    )

    run = await service.run_evaluation(
        dataset_id=dataset_id, model="gpt-4o-mini", provider="openai", metrics=["exact_match"]
    )

    assert run.results[0].cost is None


async def test_run_evaluation_continues_after_a_case_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_provider = FakeProvider(
        "openai",
        [
            make_response(provider="openai", model="gpt-4o-mini", content="Paris"),
            ProviderTimeoutError("openai", "slow"),
            ProviderTimeoutError("openai", "slow"),
            ProviderTimeoutError("openai", "slow"),
        ],
    )
    _patch_providers(monkeypatch, {"openai": fake_provider})

    service = _service(db_session)
    dataset_id = await _make_dataset(service)
    await service.add_case(
        dataset_id=dataset_id, input="What is the capital of France?", expected_output="Paris"
    )
    await service.add_case(
        dataset_id=dataset_id, input="What is the capital of Germany?", expected_output="Berlin"
    )

    run = await service.run_evaluation(
        dataset_id=dataset_id, model="gpt-4o-mini", provider="openai", metrics=["exact_match"]
    )

    assert run.status == EvaluationRunStatus.COMPLETED
    assert len(run.results) == 2
    succeeded, failed = run.results[0], run.results[1]
    assert succeeded.actual_output == "Paris"
    assert succeeded.scores == {"exact_match": 1.0}
    assert failed.actual_output.startswith("[error]")
    assert failed.scores == {}
    assert failed.tokens == 0


async def test_run_evaluation_records_result_when_one_metric_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metric evaluator raising (e.g. a malformed relevance judge
    response) drops only that metric from scores, not the whole case.
    """
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="Paris")]
    )
    _patch_providers(monkeypatch, {"openai": fake_provider})
    # answer_relevance's judge call goes through the provider registry
    # directly (not ChatCompletionService/FallbackExecutor) — patch it
    # separately, returning an unparseable response to force the failure.
    fake_judge = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="not a number")]
    )
    monkeypatch.setattr(relevance_module, "get_provider", lambda name: fake_judge)

    service = _service(db_session)
    dataset_id = await _make_dataset(service)
    await service.add_case(
        dataset_id=dataset_id, input="What is the capital of France?", expected_output="Paris"
    )

    run = await service.run_evaluation(
        dataset_id=dataset_id,
        model="gpt-4o-mini",
        provider="openai",
        metrics=["exact_match", "answer_relevance"],
    )

    result = run.results[0]
    assert result.actual_output == "Paris"
    assert result.scores == {"exact_match": 1.0}


def test_aggregate_scores_averages_per_metric() -> None:
    from app.models.evaluation import EvaluationResult

    results = [
        EvaluationResult(
            run_id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            actual_output="a",
            latency_ms=1.0,
            tokens=1,
            cost=None,
            scores={"exact_match": 1.0, "answer_relevance": 0.5},
        ),
        EvaluationResult(
            run_id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            actual_output="b",
            latency_ms=1.0,
            tokens=1,
            cost=None,
            scores={"exact_match": 0.0},
        ),
    ]

    averages = aggregate_scores(results)

    assert averages == {"exact_match": 0.5, "answer_relevance": 0.5}
