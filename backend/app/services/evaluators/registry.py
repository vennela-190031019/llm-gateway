"""Maps a metric name to an Evaluator instance.

Mirrors app.providers.registry: callers (EvaluationService) ask for an
evaluator by name — the same strings accepted in
EvaluationService.run_evaluation's `metrics` list — without needing to
import or know about any concrete evaluator class. Unlike the provider
registry, evaluators hold no client/connection to reuse, so they're
simple stateless singletons rather than lazily-constructed-and-cached
per name.
"""

from __future__ import annotations

from app.services.evaluators.base import Evaluator
from app.services.evaluators.exact_match import ExactMatchEvaluator
from app.services.evaluators.relevance import AnswerRelevanceEvaluator


class UnknownEvaluatorError(Exception):
    """Raised when asked for a metric name that isn't registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"no evaluator registered under metric name {name!r}")


_EVALUATORS: dict[str, Evaluator] = {
    ExactMatchEvaluator.name: ExactMatchEvaluator(),
    AnswerRelevanceEvaluator.name: AnswerRelevanceEvaluator(),
}


def get_evaluator(name: str) -> Evaluator:
    try:
        return _EVALUATORS[name]
    except KeyError:
        raise UnknownEvaluatorError(name) from None
