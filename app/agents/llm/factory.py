"""Builds the configured provider. The only place that knows which vendor we use."""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.agents.llm.openai_provider import OpenAIProvider
from app.agents.llm.types import LLMError, LLMProvider
from app.config import get_settings


@lru_cache
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise LLMError("OPENAI_API_KEY is not set")
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=2)
    return OpenAIProvider(client, store=settings.openai_store)
