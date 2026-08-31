"""LLM-judged relevance: how well does actual_output answer the input?

Uses the raw provider abstraction from Phase 3 directly (app.providers),
not ChatCompletionService — this judge call is a lightweight,
uncached implementation detail of the metric itself and shouldn't
participate in chat routing/retry/fallback/cost-tracking the way a
"real" completion does.
"""

from __future__ import annotations

import re

from app.providers.base import LLMProvider
from app.providers.registry import get_provider
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRole
from app.services.evaluators.base import Evaluator

_DEFAULT_JUDGE_MODEL = "gpt-4o-mini"
_DEFAULT_JUDGE_PROVIDER = "openai"

# Matches the first standalone number in the response, e.g. "0.8", "1", "0".
_SCORE_PATTERN = re.compile(r"(?<!\d)(\d(?:\.\d+)?)(?!\d)")

_PROMPT_TEMPLATE = """You are grading how relevant an AI assistant's answer is to the \
question it was asked.

Question:
{input}

Answer:
{output}

Rate the relevance of the answer to the question on a scale from 0.0 (completely \
irrelevant) to 1.0 (perfectly relevant).
Respond with ONLY the numeric score and nothing else, e.g. "0.8"."""


class RelevanceScoreParseError(Exception):
    """The judge model's response didn't contain a parseable 0.0-1.0 score.

    Raised rather than silently falling back to a default score: a
    silently-wrong number would be indistinguishable from a real score
    and would quietly corrupt the aggregate metric, whereas a raised
    error is visible and — per EvaluationService's partial-failure
    handling — just drops this one metric for this one case instead of
    poisoning the whole run.
    """

    def __init__(self, raw_response: str) -> None:
        self.raw_response = raw_response
        super().__init__(f"could not parse a relevance score out of: {raw_response!r}")


class AnswerRelevanceEvaluator(Evaluator):
    name = "answer_relevance"

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        model: str = _DEFAULT_JUDGE_MODEL,
    ) -> None:
        # Resolved lazily in evaluate() when not injected, so building the
        # registry's singleton instance never requires provider credentials.
        self._provider = provider
        self._model = model

    def _resolve_provider(self) -> LLMProvider:
        return self._provider or get_provider(_DEFAULT_JUDGE_PROVIDER)

    async def evaluate(
        self, *, case_input: str, expected_output: str | None, actual_output: str
    ) -> float:
        request = ChatCompletionRequest(
            model=self._model,
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content=_PROMPT_TEMPLATE.format(input=case_input, output=actual_output),
                )
            ],
            temperature=0.0,
        )
        response = await self._resolve_provider().complete(request)

        match = _SCORE_PATTERN.search(response.content)
        if match is None:
            raise RelevanceScoreParseError(response.content)

        score = float(match.group(1))
        if not 0.0 <= score <= 1.0:
            raise RelevanceScoreParseError(response.content)

        return score
