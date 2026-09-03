"""Evaluation dataset/run endpoints.

Gated by `require_user` (`ActiveUser`), not `require_admin` — same
reasoning as app.api.v1.prompts: evaluation datasets and runs are
per-workspace authoring/research tooling, not system-wide configuration
like the model catalog, so admin-only would make the feature unusable
for the regular users it's meant for.

`POST /runs` executes the run synchronously within the request: this
project has no background job queue, so every case in the dataset is
called and scored before the response is returned.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import ActiveUser, DbSession
from app.models.evaluation import EvaluationCase, EvaluationDataset, EvaluationRun
from app.repositories.evaluation_repository import EvaluationRepository
from app.schemas.evaluation import (
    EvaluationCaseCreate,
    EvaluationCaseRead,
    EvaluationDatasetCreate,
    EvaluationDatasetDetailRead,
    EvaluationDatasetRead,
    EvaluationResultRead,
    EvaluationRunCreate,
    EvaluationRunSummary,
)
from app.services.evaluation_service import (
    EvaluationDatasetAlreadyExistsError,
    EvaluationDatasetNotFoundError,
    EvaluationService,
    aggregate_scores,
)
from app.services.evaluators.registry import UnknownEvaluatorError

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post(
    "/datasets", response_model=EvaluationDatasetRead, status_code=status.HTTP_201_CREATED
)
async def create_dataset(
    payload: EvaluationDatasetCreate, session: DbSession, current_user: ActiveUser
) -> EvaluationDataset:
    service = EvaluationService(EvaluationRepository(session))
    try:
        dataset = await service.create_dataset(
            name=payload.name, description=payload.description, owner_id=current_user.id
        )
    except EvaluationDatasetAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await session.commit()
    return dataset


@router.post(
    "/datasets/{dataset_id}/cases",
    response_model=EvaluationCaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_case(
    dataset_id: uuid.UUID,
    payload: EvaluationCaseCreate,
    session: DbSession,
    _current_user: ActiveUser,
) -> EvaluationCase:
    service = EvaluationService(EvaluationRepository(session))
    try:
        case = await service.add_case(
            dataset_id=dataset_id, input=payload.input, expected_output=payload.expected_output
        )
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return case


@router.get("/datasets", response_model=list[EvaluationDatasetRead])
async def list_datasets(
    session: DbSession, _current_user: ActiveUser
) -> list[EvaluationDataset]:
    return list(await EvaluationRepository(session).list_datasets())


@router.get("/datasets/{dataset_id}", response_model=EvaluationDatasetDetailRead)
async def get_dataset(
    dataset_id: uuid.UUID, session: DbSession, _current_user: ActiveUser
) -> EvaluationDataset:
    dataset = await EvaluationRepository(session).get_dataset_by_id(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no evaluation dataset with id {dataset_id}",
        )
    return dataset


@router.post("/runs", response_model=EvaluationRunSummary, status_code=status.HTTP_201_CREATED)
async def start_run(
    payload: EvaluationRunCreate, session: DbSession, _current_user: ActiveUser
) -> EvaluationRunSummary:
    service = EvaluationService(EvaluationRepository(session))
    try:
        run = await service.run_evaluation(
            dataset_id=payload.dataset_id,
            model=payload.model,
            provider=payload.provider,
            metrics=payload.metrics,
        )
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnknownEvaluatorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await session.commit()
    return _run_summary(run)


@router.get("/runs/{run_id}", response_model=EvaluationRunSummary)
async def get_run(
    run_id: uuid.UUID, session: DbSession, _current_user: ActiveUser
) -> EvaluationRunSummary:
    run = await EvaluationRepository(session).get_run_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no evaluation run with id {run_id}"
        )
    return _run_summary(run)


@router.get("/runs/{run_id}/results", response_model=list[EvaluationResultRead])
async def list_run_results(
    run_id: uuid.UUID, session: DbSession, _current_user: ActiveUser
) -> list[EvaluationResultRead]:
    run = await EvaluationRepository(session).get_run_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no evaluation run with id {run_id}"
        )
    return [EvaluationResultRead.model_validate(result) for result in run.results]


def _run_summary(run: EvaluationRun) -> EvaluationRunSummary:
    return EvaluationRunSummary(
        id=run.id,
        dataset_id=run.dataset_id,
        model=run.model,
        provider=run.provider,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        case_count=len(run.results),
        average_scores=aggregate_scores(run.results),
    )
