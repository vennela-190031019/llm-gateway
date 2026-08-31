"""Evaluation dataset/case/run/result data access. No business logic —
see app.services.evaluation_service.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
)


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # Datasets

    async def create_dataset(self, dataset: EvaluationDataset) -> EvaluationDataset:
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def get_dataset_by_name(self, name: str) -> EvaluationDataset | None:
        result = await self.session.execute(
            select(EvaluationDataset).where(EvaluationDataset.name == name)
        )
        return result.scalar_one_or_none()

    async def get_dataset_by_id(self, dataset_id: uuid.UUID) -> EvaluationDataset | None:
        result = await self.session.execute(
            select(EvaluationDataset)
            .where(EvaluationDataset.id == dataset_id)
            .options(selectinload(EvaluationDataset.cases))
        )
        return result.scalar_one_or_none()

    async def list_datasets(self) -> Sequence[EvaluationDataset]:
        result = await self.session.execute(
            select(EvaluationDataset).order_by(EvaluationDataset.name)
        )
        return result.scalars().all()

    # Cases

    async def add_case(self, case: EvaluationCase) -> EvaluationCase:
        self.session.add(case)
        await self.session.flush()
        return case

    # Runs

    async def create_run(self, run: EvaluationRun) -> EvaluationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: uuid.UUID) -> EvaluationRun | None:
        result = await self.session.execute(
            select(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .options(selectinload(EvaluationRun.results))
        )
        return result.scalar_one_or_none()

    # Results

    async def add_result(self, evaluation_result: EvaluationResult) -> EvaluationResult:
        self.session.add(evaluation_result)
        await self.session.flush()
        return evaluation_result
