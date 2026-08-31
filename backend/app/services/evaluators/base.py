"""Abstract scoring interface for evaluation metrics.

Concrete evaluators (ExactMatchEvaluator, AnswerRelevanceEvaluator, ...)
score a single case's actual output against its input/expected output on
a 0.0-1.0 scale. New metrics are added by implementing this interface
and registering an instance in app.services.evaluators.registry —
EvaluationService never needs to change to support them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Evaluator(ABC):
    name: str

    @abstractmethod
    async def evaluate(
        self, *, case_input: str, expected_output: str | None, actual_output: str
    ) -> float:
        """Score `actual_output` on a 0.0 (worst) - 1.0 (best) scale."""
        raise NotImplementedError
