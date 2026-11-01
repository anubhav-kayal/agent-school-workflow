"""Typed application settings.

Everything tunable lives here: model IDs, effort levels, pricing, API versions,
safety defaults. Secrets come only from environment variables.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentName(StrEnum):
    ASSISTANT = "assistant"
    MONITOR = "monitor"
    OPTIMIZER = "optimizer"
    CREATIVE = "creative"
    REPORTER = "reporter"
    STRATEGIST = "strategist"


class LlmTier(StrEnum):
    STRATEGY = "tier_strategy"
    STANDARD = "tier_standard"
    FAST = "tier_fast"


class ModelPrice(BaseModel):
    """USD per million tokens (OpenAI Standard tier)."""

    input: float
    cached_input: float
    cache_write: float  # default 30-minute cache TTL
    output: float
    long_context_threshold: int = 272_000  # input tokens; above it the whole request costs more
    long_context_input_multiplier: float = 2.0
    long_context_output_multiplier: float = 1.5


class AgentModelConfig(BaseModel):
    tier: LlmTier
    reasoning_effort: str = "low"  # none | low | medium | high | max (model-dependent)
    max_output_tokens: int = 4096  # includes reasoning tokens
    max_tool_iterations: int = 6
    token_budget: int = 60_000  # total input+output tokens allowed per run
    use_batch: bool = False


# Approved 2026-11-01 (docs/PLAN.md). Model IDs live only here.
DEFAULT_TIERS: dict[LlmTier, str] = {
    LlmTier.STRATEGY: "gpt-6.1-sol",
    LlmTier.STANDARD: "gpt-6.1-sol",
    LlmTier.FAST: "gpt-6-luna",
}

# Source: https://developers.openai.com/api/docs/pricing (read 2026-11-01).
DEFAULT_PRICING: dict[str, ModelPrice] = {
    "gpt-6.1-sol": ModelPrice(input=2.00, cached_input=0.10, cache_write=2.50, output=10.00),
    "gpt-6.1-terra": ModelPrice(input=1.00, cached_input=0.05, cache_write=1.25, output=5.00),
    "gpt-6-luna": ModelPrice(input=0.10, cached_input=0.01, cache_write=0.125, output=0.50),
}

DEFAULT_AGENTS: dict[AgentName, AgentModelConfig] = {
    AgentName.ASSISTANT: AgentModelConfig(
        tier=LlmTier.FAST, reasoning_effort="low", max_output_tokens=2048, token_budget=40_000
    ),
    AgentName.MONITOR: AgentModelConfig(
        tier=LlmTier.FAST, reasoning_effort="low", max_output_tokens=2048, max_tool_iterations=1
    ),
    AgentName.OPTIMIZER: AgentModelConfig(tier=LlmTier.STANDARD, reasoning_effort="medium"),
    AgentName.CREATIVE: AgentModelConfig(
        tier=LlmTier.STANDARD, reasoning_effort="medium", max_output_tokens=8192, use_batch=True
    ),
    AgentName.REPORTER: AgentModelConfig(
        tier=LlmTier.STANDARD, reasoning_effort="medium", use_batch=True
    ),
    AgentName.STRATEGIST: AgentModelConfig(
        tier=LlmTier.STRATEGY,
        reasoning_effort="high",
        max_output_tokens=16_000,
        token_budget=120_000,
        use_batch=True,
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__", extra="ignore"
    )

    # --- runtime ---
    env: str = "local"
    log_level: str = "INFO"
    timezone: str = "Asia/Kolkata"
    database_url: str = (
        "postgresql+asyncpg://admissionpilot:admissionpilot@localhost:5433/admissionpilot"
    )
    redis_url: str = "redis://localhost:6380/0"
    session_secret: SecretStr = SecretStr("change-me-local-only")

    # --- safety (never relax defaults without explicit approval) ---
    dry_run: bool = True
    global_kill_switch: bool = False

    # --- LLM ---
    openai_api_key: SecretStr | None = None
    openai_store: bool = False  # never keep parent conversations on OpenAI's side
    tiers: dict[LlmTier, str] = Field(default_factory=lambda: dict(DEFAULT_TIERS))
    agents: dict[AgentName, AgentModelConfig] = Field(default_factory=lambda: dict(DEFAULT_AGENTS))
    pricing: dict[str, ModelPrice] = Field(default_factory=lambda: dict(DEFAULT_PRICING))
    batch_discount: float = 0.5  # OpenAI Batch API: 50 % of Standard, 24 h window
    usd_to_inr: float = 84.0  # placeholder default; set the real rate via USD_TO_INR
    llm_budget_alert_pct: int = 80

    # --- external API versions (TO VERIFY against current docs) ---
    meta_graph_version: str = "v24.0"
    google_ads_api_version: str = "v22"

    # --- external secrets (env only) ---
    meta_app_secret: SecretStr | None = None
    meta_verify_token: SecretStr | None = None
    meta_system_user_token: SecretStr | None = None
    whatsapp_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: SecretStr | None = None
    google_ads_developer_token: SecretStr | None = None
    google_ads_client_id: str | None = None
    google_ads_client_secret: SecretStr | None = None
    google_ads_refresh_token: SecretStr | None = None
    google_ads_login_customer_id: str | None = None

    # --- SLAs ---
    first_response_sla_seconds: int = 60

    # --- demo ---
    demo_mode: bool = False  # enables /demo/chat; never sends real WhatsApp messages

    def agent(self, name: AgentName) -> AgentModelConfig:
        return self.agents[name]

    def model_for(self, name: AgentName) -> str:
        return self.tiers[self.agents[name].tier]

    def price_for(self, model: str) -> ModelPrice:
        try:
            return self.pricing[model]
        except KeyError as exc:
            raise KeyError(f"No pricing configured for model {model!r}") from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()
