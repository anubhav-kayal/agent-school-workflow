"""OpenAIProvider against a mocked Responses endpoint (documented payload shapes).

openai>=3 sends requests through httpx2, which respx cannot intercept, so these tests
inject an httpx2.MockTransport. The conftest network guard fails any test that escapes.
"""

import json
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from app.agents.llm import LLMError, LLMRequest, ToolSpec
from app.agents.llm.openai_provider import OpenAIProvider

TOOL = ToolSpec(
    "get_school_facts",
    "Facts by topic",
    {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
        "additionalProperties": False,
    },
)
USAGE = {
    "input_tokens": 1500,
    "output_tokens": 120,
    "total_tokens": 1620,
    "input_tokens_details": {"cached_tokens": 1200, "cache_write_tokens": 0},
    "output_tokens_details": {"reasoning_tokens": 40},
}


class MockResponses:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status, self.body = status, body
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/responses"
        self.requests.append(request)
        return httpx2.Response(self.status, json=self.body)

    def provider(self) -> OpenAIProvider:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(self))
        client = AsyncOpenAI(api_key="sk-test-fake", max_retries=0, http_client=http)
        return OpenAIProvider(client)


def body(output: list[dict[str, Any]], status: str = "completed") -> dict[str, Any]:
    incomplete = {"reason": "max_output_tokens"} if status == "incomplete" else None
    return {
        "id": "resp_FAKE",
        "object": "response",
        "created_at": 0,
        "model": "gpt-6-luna",
        "status": status,
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "incomplete_details": incomplete,
        "usage": USAGE,
    }


def request(provider: OpenAIProvider) -> LLMRequest:
    return LLMRequest(
        model="gpt-6-luna",
        instructions="You are the admission assistant.",
        items=[provider.context_item("KB"), provider.user_item("Fees?")],
        tools=[TOOL],
        cache_key="school:1:assistant",
    )


async def test_tool_call_parsed_and_request_shape() -> None:
    call = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": "call_1",
        "status": "completed",
        "name": "get_school_facts",
        "arguments": json.dumps({"topic": "fees"}),
    }
    mock = MockResponses(200, body([call]))
    provider = mock.provider()
    turn = await provider.respond(request(provider))
    assert [(c.call_id, c.name, c.arguments) for c in turn.tool_calls] == [
        ("call_1", "get_school_facts", {"topic": "fees"})
    ]
    assert (turn.usage.cached_tokens, turn.usage.reasoning_tokens) == (1200, 40)
    sent = json.loads(mock.requests[0].content)
    assert sent["store"] is False
    assert sent["tools"][0]["strict"] is True
    assert sent["prompt_cache_key"] == "school:1:assistant"
    assert sent["input"][0] == {"role": "developer", "content": "KB"}
    assert "temperature" not in sent and "top_p" not in sent


async def test_text_reply() -> None:
    message = {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": "Fees are ₹85,000.", "annotations": []}],
    }
    provider = MockResponses(200, body([message])).provider()
    turn = await provider.respond(request(provider))
    assert turn.text == "Fees are ₹85,000."
    assert turn.tool_calls == []


async def test_incomplete_raises() -> None:
    provider = MockResponses(200, body([], status="incomplete")).provider()
    with pytest.raises(LLMError, match="max_output_tokens"):
        await provider.respond(request(provider))


async def test_rate_limit_becomes_llm_error() -> None:
    provider = MockResponses(429, {"error": {"message": "slow"}}).provider()
    with pytest.raises(LLMError, match="transient"):
        await provider.respond(request(provider))
