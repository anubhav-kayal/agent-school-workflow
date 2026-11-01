"""Token → money. Pure functions; prices come from config."""

from __future__ import annotations

from decimal import Decimal

from app.agents.llm import Usage
from app.config import ModelPrice

PER_MILLION = Decimal(1_000_000)


def estimate_cost_usd(
    usage: Usage, price: ModelPrice, batch_discount: float | None = None
) -> Decimal:
    fresh = max(usage.input_tokens - usage.cached_tokens - usage.cache_write_tokens, 0)
    in_mult = out_mult = Decimal(1)
    if usage.input_tokens > price.long_context_threshold:
        in_mult = Decimal(str(price.long_context_input_multiplier))
        out_mult = Decimal(str(price.long_context_output_multiplier))
    cost = (
        Decimal(fresh) * Decimal(str(price.input)) * in_mult
        + Decimal(usage.cached_tokens) * Decimal(str(price.cached_input)) * in_mult
        + Decimal(usage.cache_write_tokens) * Decimal(str(price.cache_write)) * in_mult
        + Decimal(usage.output_tokens) * Decimal(str(price.output)) * out_mult
    ) / PER_MILLION
    if batch_discount is not None:
        cost *= Decimal(str(batch_discount))
    return cost.quantize(Decimal("0.000001"))


def usd_to_inr(usd: Decimal, rate: float) -> Decimal:
    return (usd * Decimal(str(rate))).quantize(Decimal("0.0001"))
