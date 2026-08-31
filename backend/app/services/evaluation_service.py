"""Evaluation dataset/run business logic: dataset & case CRUD, plus
running every case in a dataset against a model/provider through the
pluggable evaluator registry (app.services.evaluators).

Each case's completion reports the same LLM metrics
(llm_requests_total, llm_request_latency_seconds, llm_tokens_total,
llm_cost_total, llm_errors_total) that app.api.v1.chat reports for
/chat/completions — eval traffic is real LLM traffic and should show up
in the same dashboards, not just be tracked in EvaluationResult rows.

Endpoints translate the exceptions raised here into HTTP responses —
this module has no knowledge of FastAPI.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from app.core.logging import get_logger
from app.core.metrics import (
    llm_cost_total,
    llm_errors_total,
    llm_request_latency_seconds,
    llm_requests_total,
    llm_tokens_total,
)
from app.models.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
)
from app.models.llm_request import LLMRequestStatus
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.model_repository import ModelRepository
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRole
from app.services.chat_service import ChatCompletionService
from app.services.cost import CostService, UnknownModelPricingError
from app.services.evaluators.base import Evaluator
from app.services.evaluators.registry import get_evaluator

_UNROUTED_LABEL = "none"

logger = get_logger(__name__)


class EvaluationDatasetAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"an evaluation dataset named {name!r} already exists")


class EvaluationDatasetNotFoundError(Exception):
    def __init__(self, dataset_id: uuid.UUID) -> None:
        self.dataset_id = dataset_id
        super().__init__(f"no evaluation dataset with id {dataset_id}")


class EvaluationRunNotFoundError(Exception):
    def __init__(self, run_id: uuid.UUID) -> None:
        self.run_id = run_id
        super().__init__(f"no evaluation run with id {run_id}")


def aggregate_scores(results: Sequence[EvaluationResult]) -> dict[str, float]:
    """Mean score per metric across `results`, skipping cases missing it.

    A case that failed outright (see `_run_case`) has empty `scores`, so
    it contributes to no metric's average rather than dragging every
    metric down with an arbitrary zero.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for result in results:
        for metric, score in result.scores.items():
            sums[metric] = sums.get(metric, 0.0) + score
            counts[metric] = counts.get(metric, 0) + 1
    return {metric: sums[metric] / counts[metric] for metric in sums}


class EvaluationService:
    def __init__(
        self,
        repository: EvaluationRepository,
        *,
        chat_service: ChatCompletionService | None = None,
        cost_service: CostService | None = None,
    ) -> None:
        self._repository = repository
        self._chat_service = chat_service or ChatCompletionService()
        self._cost_service = cost_service or CostService(ModelRepository(repository.session))

    async def create_dataset(
        self, *, name: str, description: str | None, owner_id: uuid.UUID
    ) -> EvaluationDataset:
        if await self._repository.get_dataset_by_name(name) is not None:
            raise EvaluationDatasetAlreadyExistsError(name)

        dataset = EvaluationDataset(name=name, description=description, owner_id=owner_id)
        return await self._repository.create_dataset(dataset)

    async def add_case(
        self, *, dataset_id: uuid.UUID, input: str, expected_output: str | None
    ) -> EvaluationCase:
        dataset = await self._repository.get_dataset_by_id(dataset_id)
        if dataset is None:
            raise EvaluationDatasetNotFoundError(dataset_id)

        case = EvaluationCase(dataset_id=dataset.id, input=input, expected_output=expected_output)
        return await self._repository.add_case(case)

    async def run_evaluation(
        self, *, dataset_id: uuid.UUID, model: str, provider: str, metrics: list[str]
    ) -> EvaluationRun:
        """Run every case in `dataset_id` through `model` and score it with `metrics`.

        `provider` is recorded on the run as the caller's intended
        provider; the LLM call itself goes through ChatCompletionService
        exactly as production /chat/completions traffic does, so the
        provider that actually serves each case still follows the normal
        model-name-based routing/fallback chain rather than being pinned.
        Forcing a specific provider would mean bypassing
        ChatCompletionService's cache/retry/fallback behavior entirely,
        which is more machinery than this phase asked for — documented
        here as a deliberate simplification.

        A failure on one case (LLM call error, evaluator error) is
        recorded on that case's result and does not abort the run — see
        `_run_case`. The run is only marked `failed` if something breaks
        outside that per-case boundary (a bug, a DB error, ...);
        otherwise it always reaches `completed`, even if every case
        individually failed.
        """
        dataset = await self._repository.get_dataset_by_id(dataset_id)
        if dataset is None:
            raise EvaluationDatasetNotFoundError(dataset_id)

        # Fail fast on an unknown metric name before creating a run row.
        evaluators = [(name, get_evaluator(name)) for name in metrics]

        run = await self._repository.create_run(
            EvaluationRun(
                dataset_id=dataset.id,
                model=model,
                provider=provider,
                status=EvaluationRunStatus.RUNNING,
            )
        )

        try:
            for case in dataset.cases:
                await self._run_case(run=run, case=case, model=model, evaluators=evaluators)
        except Exception:
            run.status = EvaluationRunStatus.FAILED
            run.completed_at = datetime.now(UTC)
            raise

        run.status = EvaluationRunStatus.COMPLETED
        run.completed_at = datetime.now(UTC)

        # Re-fetch (same identity-mapped object) with `results` eagerly
        # loaded: each result was persisted via its raw run_id FK, not
        # through the `run.results` relationship attribute, so reading
        # `run.results` directly here would trigger an async-unsafe
        # implicit lazy load instead of reflecting what's in the DB.
        loaded_run = await self._repository.get_run_by_id(run.id)
        assert loaded_run is not None  # just persisted above, in this same session
        return loaded_run

    async def _run_case(
        self,
        *,
        run: EvaluationRun,
        case: EvaluationCase,
        model: str,
        evaluators: list[tuple[str, Evaluator]],
    ) -> None:
        request = ChatCompletionRequest(
            model=model, messages=[ChatMessage(role=ChatRole.USER, content=case.input)]
        )

        started = time.monotonic()
        try:
            response = await self._chat_service.complete(request)
        except Exception as exc:
            latency_ms = (time.monotonic() - started) * 1000
            logger.warning(
                "evaluation_case_failed",
                run_id=str(run.id),
                case_id=str(case.id),
                error=str(exc),
            )
            # Mirrors app.api.v1.chat's AllProvidersExhaustedError handling:
            # a case's provider couldn't be resolved (routing exhausted, or
            # any other failure short-circuiting ChatCompletionService), so
            # there's no real provider/model to label this attempt with.
            llm_requests_total.labels(
                model=model, provider=_UNROUTED_LABEL, status=LLMRequestStatus.ERROR
            ).inc()
            llm_request_latency_seconds.labels(model=model, provider=_UNROUTED_LABEL).observe(
                latency_ms / 1000
            )
            llm_errors_total.labels(
                model=model, provider=_UNROUTED_LABEL, error_type=type(exc).__name__
            ).inc()
            await self._repository.add_result(
                EvaluationResult(
                    run_id=run.id,
                    case_id=case.id,
                    actual_output=f"[error] {exc}",
                    latency_ms=latency_ms,
                    tokens=0,
                    cost=None,
                    scores={},
                )
            )
            return

        latency_ms = (time.monotonic() - started) * 1000
        tokens = response.input_tokens + response.output_tokens

        llm_requests_total.labels(
            model=response.model, provider=response.provider, status=LLMRequestStatus.SUCCESS
        ).inc()
        llm_request_latency_seconds.labels(
            model=response.model, provider=response.provider
        ).observe(latency_ms / 1000)
        llm_tokens_total.labels(
            model=response.model, provider=response.provider, type="input"
        ).inc(response.input_tokens)
        llm_tokens_total.labels(
            model=response.model, provider=response.provider, type="output"
        ).inc(response.output_tokens)

        cost: Decimal | None
        try:
            cost = await self._cost_service.estimate_cost(
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        except UnknownModelPricingError:
            cost = None
        if cost is not None:
            llm_cost_total.labels(model=response.model, provider=response.provider).inc(
                float(cost)
            )

        scores: dict[str, float] = {}
        for metric_name, evaluator in evaluators:
            try:
                scores[metric_name] = await evaluator.evaluate(
                    case_input=case.input,
                    expected_output=case.expected_output,
                    actual_output=response.content,
                )
            except Exception as exc:
                # A single metric failing (e.g. AnswerRelevanceEvaluator's
                # RelevanceScoreParseError) shouldn't drop the whole case —
                # the other requested metrics and the actual_output itself
                # are still worth recording.
                logger.warning(
                    "evaluator_failed",
                    metric=metric_name,
                    run_id=str(run.id),
                    case_id=str(case.id),
                    error=str(exc),
                )

        await self._repository.add_result(
            EvaluationResult(
                run_id=run.id,
                case_id=case.id,
                actual_output=response.content,
                latency_ms=latency_ms,
                tokens=tokens,
                cost=cost,
                scores=scores,
            )
        )
