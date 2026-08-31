"""Case-insensitive, whitespace-normalized string equality. No LLM call."""

from __future__ import annotations

from app.services.evaluators.base import Evaluator


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


class ExactMatchEvaluator(Evaluator):
    name = "exact_match"

    async def evaluate(
        self, *, case_input: str, expected_output: str | None, actual_output: str
    ) -> float:
        # A case without an expected_output can't be exact-matched against
        # anything — treated as a non-match (0.0) rather than raising, so
        # requesting this metric never aborts the case; see
        # EvaluationService for how per-metric failures are handled too.
        if expected_output is None:
            return 0.0
        return 1.0 if _normalize(actual_output) == _normalize(expected_output) else 0.0
