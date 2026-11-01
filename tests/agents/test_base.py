import json
import time
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BudgetExceededError, Tool, log_run, run_tool_loop
from app.agents.llm import LLMError, LLMRequest, ToolSpec, Usage
from app.agents.llm.fake import ScriptedProvider, text_turn, tool_turn
from app.config import AgentName, Settings

SPEC = ToolSpec("get_school_facts", "facts", {"type": "object", "properties": {}})


def request() -> LLMRequest:
    return LLMRequest(model="m", instructions="sys", items=[{"role": "user", "content": "Fees?"}])


async def facts(args: dict[str, Any]) -> str:
    return json.dumps({"topic": args["topic"], "facts": [{"key": "fees.class_1"}]})


async def test_loop_runs_tool_then_answers() -> None:
    provider = ScriptedProvider([tool_turn("get_school_facts", topic="fees"), text_turn("₹85,000")])
    result = await run_tool_loop(provider, request(), [Tool(SPEC, facts)], 4, 50_000)
    assert result.text == "₹85,000"
    assert [c.name for c in result.calls] == ["get_school_facts"]
    second_input = provider.requests[1].items
    assert second_input[-1]["type"] == "function_call_output"
    assert "fees.class_1" in second_input[-1]["output"]
    # Regression: the model must be told which tools exist on every call.
    assert all([t.name for t in r.tools] == ["get_school_facts"] for r in provider.requests)


async def test_terminal_tool_ends_turn() -> None:
    provider = ScriptedProvider([tool_turn("escalate_to_counselor", reason="x")])
    spec = ToolSpec("escalate_to_counselor", "", {})

    async def escalate(_: dict[str, Any]) -> str:
        return "ok"

    result = await run_tool_loop(
        provider,
        request(),
        [Tool(spec, escalate)],
        4,
        50_000,
        terminal_tools=frozenset({"escalate_to_counselor"}),
    )
    assert result.stopped_by == "escalate_to_counselor"


async def test_iteration_cap() -> None:
    provider = ScriptedProvider([tool_turn("get_school_facts", topic="x")] * 3)
    with pytest.raises(LLMError, match="no final answer"):
        await run_tool_loop(provider, request(), [Tool(SPEC, facts)], 3, 50_000)


async def test_token_budget() -> None:
    provider = ScriptedProvider([text_turn("hi", Usage(input_tokens=9_000, output_tokens=2_000))])
    with pytest.raises(BudgetExceededError):
        await run_tool_loop(provider, request(), [], 3, 10_000)


async def test_log_run_records_cost(db: AsyncSession) -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    usage = Usage(input_tokens=3000, cached_tokens=2000, output_tokens=300)
    run = await log_run(
        db,
        settings,
        AgentName.ASSISTANT,
        None,
        usage,
        time.monotonic(),
        {"lead": 1},
        {"reply": "hi"},
    )
    assert run.model == "gpt-6-luna"
    assert float(run.cost_usd) == pytest.approx(0.00027)
    assert float(run.cost_inr) == pytest.approx(0.00027 * 84, rel=1e-3)
    assert run.cache_read_tokens == 2000
