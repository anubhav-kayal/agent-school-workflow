"""Scripted provider for tests: returns queued turns and records every request."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.llm.types import Item, LLMRequest, LLMTurn, ToolCall, Usage


def text_turn(text: str, usage: Usage | None = None) -> LLMTurn:
    return LLMTurn(
        text,
        [],
        usage or Usage(1000, 0, 0, 50),
        "fake-model",
        [{"role": "assistant", "content": text}],
    )


def tool_turn(name: str, call_id: str = "call_1", **arguments: object) -> LLMTurn:
    call = ToolCall(call_id, name, dict(arguments))
    item = {"type": "function_call", "call_id": call_id, "name": name}
    return LLMTurn("", [call], Usage(1000, 0, 0, 30), "fake-model", [item])


@dataclass
class ScriptedProvider:
    turns: list[LLMTurn]
    requests: list[LLMRequest] = field(default_factory=list)

    async def respond(self, request: LLMRequest) -> LLMTurn:
        self.requests.append(request)
        if not self.turns:
            raise AssertionError("ScriptedProvider ran out of turns")
        return self.turns.pop(0)

    def user_item(self, text: str) -> Item:
        return {"role": "user", "content": text}

    def assistant_item(self, text: str) -> Item:
        return {"role": "assistant", "content": text}

    def context_item(self, text: str) -> Item:
        return {"role": "developer", "content": text}

    def tool_result_item(self, call_id: str, output: str) -> Item:
        return {"type": "function_call_output", "call_id": call_id, "output": output}
