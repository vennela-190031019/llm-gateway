from __future__ import annotations

from pathlib import Path

import pytest

from app.services.router import ModelRouter, RoutingConfigError, _infer_provider


def _router() -> ModelRouter:
    return ModelRouter()  # loads the real app/core/routing_rules.yaml


def test_infer_provider_recognizes_openai_naming() -> None:
    assert _infer_provider("gpt-4o-mini") == "openai"
    assert _infer_provider("gpt-4o") == "openai"


def test_infer_provider_defaults_unknown_names_to_ollama() -> None:
    assert _infer_provider("llama3.1") == "ollama"
    assert _infer_provider("mistral") == "ollama"


def test_get_candidates_prioritizes_requested_model_first() -> None:
    candidates = _router().get_candidates("llama3.1", task_type="coding")

    assert candidates[0] == ("ollama", "llama3.1")
    assert ("openai", "gpt-4o") in candidates
    assert ("openai", "gpt-4o-mini") in candidates


def test_get_candidates_dedupes_requested_model_already_in_rule() -> None:
    candidates = _router().get_candidates("gpt-4o-mini", task_type="summarization")

    assert candidates == [("openai", "gpt-4o-mini"), ("ollama", "llama3.1")]


def test_get_candidates_falls_back_to_default_for_unrecognized_task_type() -> None:
    candidates = _router().get_candidates("some-model", task_type="not-a-real-task")

    assert candidates[0] == ("ollama", "some-model")
    assert ("openai", "gpt-4o-mini") in candidates
    assert ("openai", "gpt-4o") in candidates


def test_get_candidates_falls_back_to_default_when_task_type_missing() -> None:
    candidates = _router().get_candidates("gpt-4o-mini", task_type=None)

    assert candidates == [("openai", "gpt-4o-mini"), ("openai", "gpt-4o")]


def test_load_config_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RoutingConfigError):
        ModelRouter(config_path=tmp_path / "does-not-exist.yaml")


def test_load_config_raises_for_invalid_yaml(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("not: valid: yaml: [")

    with pytest.raises(RoutingConfigError):
        ModelRouter(config_path=bad_file)


def test_load_config_raises_for_schema_mismatch(tmp_path: Path) -> None:
    config_file = tmp_path / "rules.yaml"
    config_file.write_text("rules: not-a-mapping\nfallback_chain: []\n")

    with pytest.raises(RoutingConfigError):
        ModelRouter(config_path=config_file)


def test_load_config_raises_when_default_rule_missing(tmp_path: Path) -> None:
    config_file = tmp_path / "rules.yaml"
    config_file.write_text(
        "rules:\n"
        "  coding:\n"
        "    tier: high-capability\n"
        "    models: [gpt-4o]\n"
        "fallback_chain: [openai]\n"
    )

    with pytest.raises(RoutingConfigError):
        ModelRouter(config_path=config_file)


def test_get_candidates_raises_when_no_candidate_provider_is_routable(tmp_path: Path) -> None:
    config_file = tmp_path / "rules.yaml"
    config_file.write_text(
        "rules:\n"
        "  default:\n"
        "    tier: balanced\n"
        "    models: [gpt-4o]\n"
        "fallback_chain: []\n"
    )
    router = ModelRouter(config_path=config_file)

    with pytest.raises(RoutingConfigError):
        router.get_candidates("gpt-4o")
