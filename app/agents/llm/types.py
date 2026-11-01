from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

# Transcript items are provider-opaque dicts; agents only create them via the provider helpers.
Item = dict[str, Any]


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema; strict: every property required, no extras


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0  # includes cached tokens
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0  # includes reasoning tokens
    reasoning_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(*(a + b for a, b in zip(_astuple(self), _astuple(other), strict=True)))


def _astuple(u: Usage) -> tuple[int, ...]:
    return (
        u.input_tokens,
        u.cached_tokens,
        u.cache_write_tokens,
        u.output_tokens,
        u.reasoning_tokens,
    )


@dataclass(frozen=True)
class LLMRequest:
    model: str
    instructions: str  # static system prompt (cached prefix)
    items: list[Item]  # context items (KB first) + conversation
    tools: list[ToolSpec] = field(default_factory=list)
    reasoning_effort: str = "low"
    max_output_tokens: int = 2048
    cache_key: str | None = None  # per-tenant cache accounting


@dataclass(frozen=True)
class LLMTurn:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    model: str
    output_items: list[Item]  # append to the transcript before tool results


class LLMProvider(Protocol):
    async def respond(self, request: LLMRequest) -> LLMTurn: ...

    def user_item(self, text: str) -> Item: ...

    def assistant_item(self, text: str) -> Item: ...

    def context_item(self, text: str) -> Item:
        """Operator-provided context (e.g. the school KB) placed before the conversation."""
        ...

    def tool_result_item(self, call_id: str, output: str) -> Item: ...
