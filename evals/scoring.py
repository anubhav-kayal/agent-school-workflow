"""Deterministic checks for assistant eval scenarios (no model calls here)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.language import detect_language


@dataclass
class Transcript:
    """What happened in one scenario run."""

    replies: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    escalated: bool = False
    booked: bool = False
    buttons_offered: int = 0
    slot_labels: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    cost_inr: float = 0.0
    llm_calls: int = 0


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def score(expect: dict[str, Any], t: Transcript) -> list[Check]:
    last = t.replies[-1] if t.replies else ""
    every = " ".join(t.replies)
    checks: list[Check] = []
    for tool in expect.get("must_call", []):
        checks.append(Check(f"calls {tool}", tool in t.tools, str(t.tools)))
    for tool in expect.get("must_not_call", []):
        checks.append(Check(f"never calls {tool}", tool not in t.tools, str(t.tools)))
    if "escalate" in expect:
        checks.append(Check("escalation", t.escalated == expect["escalate"], f"got {t.escalated}"))
    if "language" in expect and last:
        got = detect_language(last)
        checks.append(Check(f"replies in {expect['language']}", got == expect["language"], got))
    if "contains_any" in expect:
        needles = [str(n).lower() for n in expect["contains_any"]]
        hit = any(n in every.lower() for n in needles)
        checks.append(Check(f"mentions one of {needles}", hit, last[:120]))
    for bad in expect.get("must_not_contain", []):
        checks.append(Check(f"does not say {bad!r}", bad.lower() not in every.lower(), ""))
    if "max_words" in expect:
        longest = max((_words(r) for r in t.replies), default=0)
        checks.append(
            Check(f"≤ {expect['max_words']} words", longest <= expect["max_words"], str(longest))
        )
    if "route" in expect:
        checks.append(Check(f"route {expect['route']}", expect["route"] in t.routes, str(t.routes)))
    if "no_reply" in expect:
        checks.append(Check("sends nothing", (not t.replies) == expect["no_reply"], str(t.replies)))
    if "slot_labels_contain" in expect:
        want = str(expect["slot_labels_contain"])
        ok = bool(t.slot_labels) and all(want in label for label in t.slot_labels)
        checks.append(Check(f"every offered slot is {want!r}", ok, str(t.slot_labels)))
    if "booked" in expect:
        checks.append(Check("visit booked", t.booked == expect["booked"], ""))
    if "slot_buttons" in expect:
        checks.append(Check("offers slot buttons", t.buttons_offered > 0, str(t.buttons_offered)))
    return checks
