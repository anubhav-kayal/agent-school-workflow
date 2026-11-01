import pytest

from app.config import AgentName, Settings


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
        model = s.agent(name).model
        assert s.price_for(model).input > 0


def test_model_assignment_matches_spec() -> None:
    s = make_settings()
    assert s.agent(AgentName.STRATEGIST).model == "claude-opus-5-5"
    assert s.agent(AgentName.STRATEGIST).use_batch is True
    for name in (AgentName.OPTIMIZER, AgentName.CREATIVE, AgentName.REPORTER):
        assert s.agent(name).model == "claude-sonnet-5-5"
    for name in (AgentName.ASSISTANT, AgentName.MONITOR):
        assert s.agent(name).model == "claude-haiku-5-5"


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
    s = make_settings(anthropic_api_key="sk-fake-123")
    assert "sk-fake-123" not in repr(s)
