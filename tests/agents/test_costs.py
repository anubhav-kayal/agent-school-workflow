from decimal import Decimal

from app.agents.costs import estimate_cost_usd, usd_to_inr
from app.agents.llm import Usage
from app.config import ModelPrice

LUNA = ModelPrice(input=0.10, cached_input=0.01, cache_write=0.125, output=0.50)


def test_cached_tokens_billed_at_cached_rate() -> None:
    u = Usage(input_tokens=3000, cached_tokens=2000, output_tokens=300)
    # 1000*0.10 + 2000*0.01 + 300*0.50 = 100 + 20 + 150 = 270 per M → $0.00027
    assert estimate_cost_usd(u, LUNA) == Decimal("0.000270")


def test_cache_writes_billed_separately() -> None:
    u = Usage(input_tokens=2000, cache_write_tokens=2000, output_tokens=0)
    assert estimate_cost_usd(u, LUNA) == Decimal("0.000250")


def test_long_context_surcharge_applies_to_whole_request() -> None:
    u = Usage(input_tokens=300_000, output_tokens=1_000_000)
    # 300k*0.10*2 + 1M*0.50*1.5 = 60,000 + 750,000 per M = $0.81
    assert estimate_cost_usd(u, LUNA) == Decimal("0.810000")


def test_batch_discount_and_inr() -> None:
    u = Usage(input_tokens=100_000, output_tokens=0)  # below the long-context threshold
    usd = estimate_cost_usd(u, LUNA, batch_discount=0.5)
    assert usd == Decimal("0.005000")
    assert usd_to_inr(usd, 84.0) == Decimal("0.4200")
