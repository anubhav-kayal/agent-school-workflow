"""Shared agent runtime: tool loop with caps, retries, cost and agent_runs logging.

Agents describe *what* (prompt, tools, handlers); this module handles *how*.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.agents.costs import estimate_cost_usd, usd_to_inr
from app.agents.llm import LLMError, LLMProvider, LLMRequest, LLMTurn, ToolCall, ToolSpec, Usage
from app.agents.llm.types import Item
from app.config import AgentName, Settings
from app.models import AgentRun

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


class BudgetExceededError(LLMError):
    pass


@dataclass
class Tool:
    spec: ToolSpec
    handler: ToolHandler


@dataclass
class LoopResult:
    text: str
    usage: Usage
    calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    stopped_by: str | None = None  # a tool name that ends the turn, if any


def _transient(exc: BaseException) -> bool:
    return isinstance(exc, LLMError) and str(exc).startswith("transient")


async def _respond(provider: LLMProvider, request: LLMRequest) -> LLMTurn:
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(_transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    ):
        with attempt:
            return await provider.respond(request)
    raise AssertionError("unreachable")


async def run_tool_loop(
    provider: LLMProvider,
    request: LLMRequest,
    tools: list[Tool],
    max_iterations: int,
    token_budget: int,
    terminal_tools: frozenset[str] = frozenset(),
) -> LoopResult:
    """Call the model until it answers in text, a terminal tool runs, or a cap is hit."""
    by_name = {t.spec.name: t for t in tools}
    items: list[Item] = list(request.items)
    result = LoopResult(text="", usage=Usage())
    for _ in range(max_iterations):
        turn = await _respond(provider, LLMRequest(**{**request.__dict__, "items": list(items)}))
        result.iterations += 1
        result.usage = result.usage + turn.usage
        if result.usage.input_tokens + result.usage.output_tokens > token_budget:
            raise BudgetExceededError(f"token budget {token_budget} exceeded")
        if not turn.tool_calls:
            result.text = turn.text
            return result
        items.extend(turn.output_items)
        for call in turn.tool_calls:
            result.calls.append(call)
            tool = by_name.get(call.name)
            output = await tool.handler(call.arguments) if tool else f"unknown tool {call.name}"
            items.append(provider.tool_result_item(call.call_id, output))
            if call.name in terminal_tools:
                result.stopped_by = call.name
        if result.stopped_by:
            result.text = turn.text
            return result
    raise LLMError(f"no final answer after {max_iterations} iterations")


async def log_run(
    db: AsyncSession,
    settings: Settings,
    agent: AgentName,
    school_id: int | None,
    usage: Usage,
    started: float,
    input_summary: dict[str, Any],
    output: dict[str, Any],
    status: str = "ok",
    error: str | None = None,
) -> AgentRun:
    model = settings.model_for(agent)
    usd = estimate_cost_usd(usage, settings.price_for(model))
    run = AgentRun(
        agent=agent.value,
        school_id=school_id,
        model=model,
        status=status,
        tokens_in=usage.input_tokens,
        tokens_out=usage.output_tokens,
        cache_read_tokens=usage.cached_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        cost_usd=usd,
        cost_inr=usd_to_inr(usd, settings.usd_to_inr),
        latency_ms=int((time.monotonic() - started) * 1000),
        input_summary=input_summary,
        output=json.loads(json.dumps(output, default=str)),
        error=error,
    )
    db.add(run)
    await db.flush()
    return run
