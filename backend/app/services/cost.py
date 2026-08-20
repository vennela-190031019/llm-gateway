"""Cost estimation for completed chat requests.

Pricing lives in the DB (Phase 2's LLMModel catalog), not hardcoded here
or in the chat service — this is the only place that turns a token count
and a catalog price into a dollar figure.
"""

from __future__ import annotations

from decimal import Decimal

from app.repositories.model_repository import ModelRepository

_PRICING_UNIT_TOKENS = Decimal(1000)


class UnknownModelPricingError(Exception):
    """No catalog entry (and therefore no known price) for this model/provider."""

    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        super().__init__(f"no pricing found for provider={provider!r} model={model!r}")


class CostService:
    def __init__(self, model_repository: ModelRepository) -> None:
        self._model_repository = model_repository

    async def estimate_cost(
        self, *, provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> Decimal:
        """Estimate cost in USD from the catalog's per-1k-token pricing.

        Raises UnknownModelPricingError if `model`/`provider` isn't in the
        catalog — callers should treat that as "cost unknown", not fail
        the whole request over it.
        """
        catalog_entry = await self._model_repository.get_by_name_and_provider(model, provider)
        if catalog_entry is None:
            raise UnknownModelPricingError(provider, model)

        input_cost = (
            Decimal(input_tokens) / _PRICING_UNIT_TOKENS
        ) * catalog_entry.input_price_per_1k
        output_cost = (
            Decimal(output_tokens) / _PRICING_UNIT_TOKENS
        ) * catalog_entry.output_price_per_1k
        return input_cost + output_cost
