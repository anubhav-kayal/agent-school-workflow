"""Tools for the admission assistant. Handlers only read/write through services."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import Tool
from app.agents.llm import ToolSpec
from app.formatting import IST, format_slot
from app.models import Lead
from app.models.enums import Actor, Language, LeadEventType, LeadStatus
from app.models.leads import LeadEvent
from app.services import kb, visits


@dataclass
class TurnState:
    """What the tools did during one assistant turn; the caller acts on it."""

    offered_slots: list[tuple[int, str]] = field(default_factory=list)  # (slot_id, label)
    booked_slot_id: int | None = None
    escalations: list[tuple[str, str]] = field(default_factory=list)  # (reason, urgency)
    not_interested: str | None = None


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


SPECS = {
    "get_school_facts": ToolSpec(
        "get_school_facts",
        "Verified facts about the school for one topic. The ONLY source of facts you may state.",
        _obj({"topic": {"type": "string", "description": "One of the topics listed in context."}}),
    ),
    "get_visit_slots": ToolSpec(
        "get_visit_slots",
        "Open campus-visit slots. Dates are YYYY-MM-DD (IST); null means from tomorrow / +14 days.",
        _obj({"from_date": {"type": ["string", "null"]}, "to_date": {"type": ["string", "null"]}}),
    ),
    "book_visit": ToolSpec(
        "book_visit",
        "Book (or move) the parent's campus visit.",
        _obj({"slot_id": {"type": "integer"}}),
    ),
    "set_language": ToolSpec(
        "set_language",
        "Record the parent's preferred language.",
        _obj({"language": {"type": "string", "enum": ["en", "hi", "hinglish"]}}),
    ),
    "escalate_to_counselor": ToolSpec(
        "escalate_to_counselor",
        "Hand over to a human counselor (missing fact, discount, complaint, asks for a human).",
        _obj(
            {
                "reason": {"type": "string"},
                "urgency": {"type": "string", "enum": ["low", "normal", "high"]},
            }
        ),
    ),
    "mark_not_interested": ToolSpec(
        "mark_not_interested",
        "Parent clearly is not interested.",
        _obj({"reason": {"type": "string"}}),
    ),
}


def build_tools(db: AsyncSession, lead: Lead, now: datetime, state: TurnState) -> list[Tool]:
    lang = "hi" if lead.language == Language.HI else "en"

    async def get_school_facts(args: dict[str, Any]) -> str:
        facts = await kb.verified_facts(db, lead.school_id, args["topic"])
        if not facts:
            return json.dumps(
                {
                    "facts": [],
                    "instruction": "Not in verified KB. Do not guess; "
                    "tell the parent a counselor will confirm and escalate.",
                }
            )
        return json.dumps(
            {"facts": [{"id": f.id, "key": f.key, "value": f.value} for f in facts]},
            ensure_ascii=False,
        )

    async def get_visit_slots(args: dict[str, Any]) -> str:
        start = _parse_day(args.get("from_date")) or now
        end = _parse_day(args.get("to_date"), end=True) or now + timedelta(days=14)
        slots = await visits.open_slots(db, lead.school_id, max(start, now), end, limit=3)
        state.offered_slots = [(s.id, format_slot(s.starts_at, lang)) for s in slots]
        return json.dumps(
            {
                "slots": [{"slot_id": i, "label": label} for i, label in state.offered_slots],
                "note": "Slots are shown to the parent as buttons automatically.",
            },
            ensure_ascii=False,
        )

    async def book_visit(args: dict[str, Any]) -> str:
        try:
            await visits.book_visit(db, lead, int(args["slot_id"]), Actor.ASSISTANT)
        except visits.SlotUnavailableError:
            return json.dumps({"ok": False, "error": "slot unavailable; offer other slots"})
        state.booked_slot_id = int(args["slot_id"])
        return json.dumps({"ok": True})

    async def set_language(args: dict[str, Any]) -> str:
        lead.language = Language(args["language"])
        return json.dumps({"ok": True})

    async def escalate(args: dict[str, Any]) -> str:
        state.escalations.append((args["reason"], args["urgency"]))
        return json.dumps({"ok": True, "tell_parent": "A counselor will get back to them soon."})

    async def not_interested(args: dict[str, Any]) -> str:
        state.not_interested = args["reason"]
        lead.status = LeadStatus.NOT_INTERESTED
        db.add(
            LeadEvent(
                lead_id=lead.id,
                school_id=lead.school_id,
                event=LeadEventType.NOT_INTERESTED,
                actor=Actor.ASSISTANT,
                note=args["reason"][:500],
            )
        )
        return json.dumps({"ok": True})

    handlers = {
        "get_school_facts": get_school_facts,
        "get_visit_slots": get_visit_slots,
        "book_visit": book_visit,
        "set_language": set_language,
        "escalate_to_counselor": escalate,
        "mark_not_interested": not_interested,
    }
    return [Tool(SPECS[name], handler) for name, handler in handlers.items()]


def _parse_day(value: str | None, end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        day = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=IST)
    except ValueError:
        return None
    return day + timedelta(days=1) if end else day
