from __future__ import annotations

import pytest

from app.providers.exceptions import ProviderTimeoutError
from app.services.evaluators.exact_match import ExactMatchEvaluator
from app.services.evaluators.registry import UnknownEvaluatorError, get_evaluator
from app.services.evaluators.relevance import AnswerRelevanceEvaluator, RelevanceScoreParseError

from .fakes import FakeProvider, make_response


async def test_exact_match_scores_identical_strings() -> None:
    evaluator = ExactMatchEvaluator()

    score = await evaluator.evaluate(
        case_input="what is 2+2?", expected_output="4", actual_output="4"
    )

    assert score == 1.0


async def test_exact_match_is_case_and_whitespace_insensitive() -> None:
    evaluator = ExactMatchEvaluator()

    score = await evaluator.evaluate(
        case_input="greet", expected_output="Hello World", actual_output="  hello   world  "
    )

    assert score == 1.0


async def test_exact_match_scores_different_strings_as_zero() -> None:
    evaluator = ExactMatchEvaluator()

    score = await evaluator.evaluate(
        case_input="what is 2+2?", expected_output="4", actual_output="5"
    )

    assert score == 0.0


async def test_exact_match_without_expected_output_scores_zero() -> None:
    evaluator = ExactMatchEvaluator()

    score = await evaluator.evaluate(
        case_input="what is 2+2?", expected_output=None, actual_output="4"
    )

    assert score == 0.0


async def test_answer_relevance_parses_numeric_score_from_judge(
) -> None:
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="0.8")]
    )
    evaluator = AnswerRelevanceEvaluator(provider=fake_provider)

    score = await evaluator.evaluate(
        case_input="What is the capital of France?",
        expected_output=None,
        actual_output="Paris is the capital of France.",
    )

    assert score == 0.8
    assert fake_provider.calls == 1


async def test_answer_relevance_parses_score_embedded_in_sentence() -> None:
    fake_provider = FakeProvider(
        "openai",
        [
            make_response(
                provider="openai", model="gpt-4o-mini", content="The score is 0.5 out of 1.0"
            )
        ],
    )
    evaluator = AnswerRelevanceEvaluator(provider=fake_provider)

    score = await evaluator.evaluate(
        case_input="q", expected_output=None, actual_output="a"
    )

    assert score == 0.5


async def test_answer_relevance_raises_on_malformed_response() -> None:
    fake_provider = FakeProvider(
        "openai",
        [make_response(provider="openai", model="gpt-4o-mini", content="that seems relevant")],
    )
    evaluator = AnswerRelevanceEvaluator(provider=fake_provider)

    with pytest.raises(RelevanceScoreParseError):
        await evaluator.evaluate(case_input="q", expected_output=None, actual_output="a")


async def test_answer_relevance_raises_on_out_of_range_score() -> None:
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="5")]
    )
    evaluator = AnswerRelevanceEvaluator(provider=fake_provider)

    with pytest.raises(RelevanceScoreParseError):
        await evaluator.evaluate(case_input="q", expected_output=None, actual_output="a")


async def test_answer_relevance_propagates_provider_errors() -> None:
    fake_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")])
    evaluator = AnswerRelevanceEvaluator(provider=fake_provider)

    with pytest.raises(ProviderTimeoutError):
        await evaluator.evaluate(case_input="q", expected_output=None, actual_output="a")


def test_registry_returns_exact_match_evaluator() -> None:
    evaluator = get_evaluator("exact_match")

    assert isinstance(evaluator, ExactMatchEvaluator)


def test_registry_returns_answer_relevance_evaluator() -> None:
    evaluator = get_evaluator("answer_relevance")

    assert isinstance(evaluator, AnswerRelevanceEvaluator)


def test_registry_raises_for_unknown_metric() -> None:
    with pytest.raises(UnknownEvaluatorError):
        get_evaluator("does-not-exist")
