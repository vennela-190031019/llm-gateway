"""Resolves a task_type + requested model into an ordered candidate list.

Reads app/core/routing_rules.yaml (path from settings.routing_rules_path):
each task_type maps to a tier and an ordered list of fallback model
names, and a top-level fallback_chain lists the providers we're allowed
to route to. Model names aren't tagged with a provider in the YAML, so
`_infer_provider` derives one from naming convention — only "openai" and
"ollama" are registered today (see app.providers.registry), so anything
that doesn't look like an OpenAI model name is assumed to be served
locally via Ollama.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

_DEFAULT_RULE_KEY = "default"
_OPENAI_MODEL_PREFIXES = ("gpt-", "chatgpt-", "o1", "o3", "o4")


class RoutingConfigError(Exception):
    """The routing rules file is missing, malformed, or misconfigured."""


class RoutingRule(BaseModel):
    tier: str
    models: list[str]


class RoutingConfig(BaseModel):
    rules: dict[str, RoutingRule]
    fallback_chain: list[str]


def _infer_provider(model_name: str) -> str:
    if model_name.lower().startswith(_OPENAI_MODEL_PREFIXES):
        return "openai"
    return "ollama"


class ModelRouter:
    def __init__(self, config_path: str | Path | None = None) -> None:
        path = Path(config_path or get_settings().routing_rules_path)
        self._config = self._load_config(path)

    @staticmethod
    def _load_config(path: Path) -> RoutingConfig:
        try:
            raw = yaml.safe_load(path.read_text())
        except OSError as exc:
            raise RoutingConfigError(f"could not read routing rules at {path}: {exc}") from exc
        except yaml.YAMLError as exc:
            raise RoutingConfigError(f"invalid YAML in routing rules at {path}: {exc}") from exc

        try:
            config = RoutingConfig.model_validate(raw)
        except ValidationError as exc:
            raise RoutingConfigError(f"invalid routing rules at {path}: {exc}") from exc

        if _DEFAULT_RULE_KEY not in config.rules:
            raise RoutingConfigError(
                f"routing rules at {path} must define a '{_DEFAULT_RULE_KEY}' rule"
            )
        return config

    def get_candidates(
        self, requested_model: str, task_type: str | None = None
    ) -> list[tuple[str, str]]:
        """Return an ordered list of (provider_name, model_name) to try.

        The requested model is tried first, then the rest of the matching
        task_type's rule (or "default" if task_type is missing/unknown),
        skipping duplicates.
        """
        rule = self._config.rules.get(task_type) if task_type else None
        if rule is None:
            rule = self._config.rules[_DEFAULT_RULE_KEY]

        seen: set[str] = set()
        candidates: list[tuple[str, str]] = []
        for model in (requested_model, *rule.models):
            if model in seen:
                continue
            seen.add(model)

            provider = _infer_provider(model)
            if provider not in self._config.fallback_chain:
                continue
            candidates.append((provider, model))

        if not candidates:
            raise RoutingConfigError(
                f"no routable candidates for model={requested_model!r} task_type={task_type!r}"
            )
        return candidates


@lru_cache
def get_router() -> ModelRouter:
    return ModelRouter()
