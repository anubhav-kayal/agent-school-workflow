"""OpenAI Responses API provider. The only module that imports the openai SDK.

Docs: https://developers.openai.com/api/docs/guides/function-calling.md
"""

from __future__ import annotations

import json
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.responses import Response

from app.agents.llm.types import Item, LLMError, LLMRequest, LLMTurn, ToolCall, ToolSpec, Usage


class OpenAIProvider:
    def __init__(self, client: AsyncOpenAI, store: bool = False) -> None:
        self._client = client
        self._store = store

    async def respond(self, request: LLMRequest) -> LLMTurn:
        params: dict[str, Any] = {
            "model": request.model,
            "instructions": request.instructions,
            "input": request.items,
            "reasoning": {"effort": request.reasoning_effort},
            "max_output_tokens": request.max_output_tokens,
            "store": self._store,
            "include": ["reasoning.encrypted_content"],
        }
        if request.tools:
            params["tools"] = [_tool(t) for t in request.tools]
        if request.cache_key:
            params["prompt_cache_key"] = request.cache_key
        try:
            resp: Response = await self._client.responses.create(**params)
        except (RateLimitError, APIConnectionError) as exc:
            raise LLMError(f"transient: {exc}") from exc
        except APIStatusError as exc:
            raise LLMError(f"api error {exc.status_code}: {exc.message}") from exc
        if resp.status == "incomplete":
            reason = resp.incomplete_details.reason if resp.incomplete_details else "unknown"
            raise LLMError(f"incomplete response: {reason}")
        calls = [
            ToolCall(item.call_id, item.name, json.loads(item.arguments or "{}"))
            for item in resp.output
            if item.type == "function_call"
        ]
        return LLMTurn(
            text=resp.output_text,
            tool_calls=calls,
            usage=_usage(resp.usage),
            model=resp.model,
            output_items=[item.model_dump(exclude_none=True) for item in resp.output],
        )

    def user_item(self, text: str) -> Item:
        return {"role": "user", "content": text}

    def assistant_item(self, text: str) -> Item:
        return {"role": "assistant", "content": text}

    def context_item(self, text: str) -> Item:
        return {"role": "developer", "content": text}

    def tool_result_item(self, call_id: str, output: str) -> Item:
        return {"type": "function_call_output", "call_id": call_id, "output": output}


def _tool(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "name": spec.name,
        "description": spec.description,
        "parameters": spec.parameters,
        "strict": True,
    }


def _usage(u: Any) -> Usage:
    if u is None:
        return Usage()
    inp = getattr(u, "input_tokens_details", None)
    out = getattr(u, "output_tokens_details", None)
    return Usage(
        input_tokens=u.input_tokens,
        cached_tokens=getattr(inp, "cached_tokens", 0) or 0,
        cache_write_tokens=getattr(inp, "cache_write_tokens", 0) or 0,
        output_tokens=u.output_tokens,
        reasoning_tokens=getattr(out, "reasoning_tokens", 0) or 0,
    )
