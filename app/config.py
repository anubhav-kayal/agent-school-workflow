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


class ModelPrice(BaseModel):
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write_5m: float
    cache_write_1h: float


class AgentModelConfig(BaseModel):
    model: str
    effort: str = "medium"
    max_output_tokens: int = 4096
    max_tool_iterations: int = 6
    token_budget: int = 60_000  # total input+output tokens allowed per run
    use_batch: bool = False


# TO VERIFY: list prices (USD / MTok) — confirm against anthropic.com/pricing before go-live.
DEFAULT_PRICING: dict[str, ModelPrice] = {
    "claude-opus-5-5": ModelPrice(
        input=4.00, output=20.00, cache_read=0.20, cache_write_5m=5.00, cache_write_1h=8.00
    ),
    "claude-sonnet-5-5": ModelPrice(
        input=2.00, output=10.00, cache_read=0.20, cache_write_5m=2.50, cache_write_1h=4.00
    ),
    "claude-haiku-5-5": ModelPrice(
        input=0.10, output=0.50, cache_read=0.01, cache_write_5m=0.125, cache_write_1h=0.20
    ),
}

DEFAULT_AGENTS: dict[AgentName, AgentModelConfig] = {
    AgentName.ASSISTANT: AgentModelConfig(
        model="claude-haiku-5-5", effort="low", max_output_tokens=1024, token_budget=30_000
    ),
    AgentName.MONITOR: AgentModelConfig(
        model="claude-haiku-5-5", effort="low", max_output_tokens=1024, max_tool_iterations=1
    ),
    AgentName.OPTIMIZER: AgentModelConfig(model="claude-sonnet-5-5", effort="medium"),
    AgentName.CREATIVE: AgentModelConfig(
        model="claude-sonnet-5-5", effort="medium", max_output_tokens=8192, use_batch=True
    ),
    AgentName.REPORTER: AgentModelConfig(
        model="claude-sonnet-5-5", effort="medium", max_output_tokens=4096, use_batch=True
    ),
    AgentName.STRATEGIST: AgentModelConfig(
        model="claude-opus-5-5",
        effort="high",
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
    anthropic_api_key: SecretStr | None = None
    agents: dict[AgentName, AgentModelConfig] = Field(default_factory=lambda: dict(DEFAULT_AGENTS))
    pricing: dict[str, ModelPrice] = Field(default_factory=lambda: dict(DEFAULT_PRICING))
    batch_discount: float = 0.5  # TO VERIFY: Message Batches API discount
    usd_to_inr: float = 84.0  # TO VERIFY: set the rate finance wants to use
    cache_ttl_assistant: str = "5m"  # "5m" or "1h"
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

    def agent(self, name: AgentName) -> AgentModelConfig:
        return self.agents[name]

    def price_for(self, model: str) -> ModelPrice:
        try:
            return self.pricing[model]
        except KeyError as exc:
            raise KeyError(f"No pricing configured for model {model!r}") from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()
