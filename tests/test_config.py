import pytest

from app.config import AgentName, LlmTier, Settings


def make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_safety_defaults() -> None:
    s = make_settings()
    assert s.dry_run is True
    assert s.global_kill_switch is False
    assert s.timezone == "Asia/Kolkata"


def test_every_agent_has_pricing() -> None:
    s = make_settings()
    for name in AgentName:
        assert s.price_for(s.model_for(name)).input > 0


def test_tier_mapping_matches_approved_plan() -> None:
    s = make_settings()
    assert s.model_for(AgentName.STRATEGIST) == "gpt-6.1-sol"
    assert s.agent(AgentName.STRATEGIST).use_batch is True
    for name in (AgentName.OPTIMIZER, AgentName.CREATIVE, AgentName.REPORTER):
        assert s.agent(name).tier is LlmTier.STANDARD
    for name in (AgentName.ASSISTANT, AgentName.MONITOR):
        assert s.model_for(name) == "gpt-6-luna"


def test_tier_override_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIERS__TIER_FAST", "gpt-6.1-terra")
    assert make_settings().model_for(AgentName.ASSISTANT) == "gpt-6.1-terra"


def test_demo_mode_off_and_store_off_by_default() -> None:
    s = make_settings()
    assert s.demo_mode is False
    assert s.openai_store is False


def test_unknown_model_price_raises() -> None:
    with pytest.raises(KeyError, match="No pricing"):
        make_settings().price_for("not-a-model")


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("USD_TO_INR", "85.5")
    s = make_settings()
    assert s.dry_run is False
    assert s.usd_to_inr == 85.5


def test_secrets_are_masked() -> None:
    s = make_settings(openai_api_key="sk-fake-123")
    assert "sk-fake-123" not in repr(s)
