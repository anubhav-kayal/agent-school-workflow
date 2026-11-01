"""Deterministic routing of inbound WhatsApp messages. Anything decided here skips the LLM."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.models.enums import Language, LeadEventType

# Exact-match (after normalisation) so "don't stop sending" is NOT an opt-out.
STOP_PHRASES = {
    "stop",
    "stop messages",
    "unsubscribe",
    "stop all",
    "opt out",
    "optout",
    "cancel messages",
    "बंद",
    "बंद करो",
    "बंद करें",
    "मैसेज बंद करें",
    "मैसेज बंद करो",
    "band karo",
    "band karein",
}
OPT_OUT_BUTTON = "optout"
SLOT_PREFIX = "slot:"
LANGUAGE_PREFIX = "lang:"  # lang:en | lang:hi | lang:hinglish
COUNSELOR_PREFIX = "lead:"  # lead:<id>:<event>
COUNSELOR_EVENTS = {
    "visit_booked": LeadEventType.VISIT_BOOKED,
    "visited": LeadEventType.VISITED,
    "admitted": LeadEventType.ADMITTED,
    "not_interested": LeadEventType.NOT_INTERESTED,
}


class Route(StrEnum):
    OPT_OUT = "opt_out"
    BOOK_SLOT = "book_slot"
    COUNSELOR_STATUS = "counselor_status"
    SET_LANGUAGE = "set_language"
    LLM = "llm"


@dataclass(frozen=True)
class Decision:
    route: Route
    slot_id: int | None = None
    lead_id: int | None = None
    event: LeadEventType | None = None
    language: Language | None = None


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = re.sub(r"[\s।.!]+$", "", text)  # trailing punctuation incl. Devanagari danda
    return re.sub(r"\s+", " ", text)


def route_inbound(text: str | None, button_id: str | None) -> Decision:
    if button_id:
        if button_id == OPT_OUT_BUTTON:
            return Decision(Route.OPT_OUT)
        if button_id.startswith(LANGUAGE_PREFIX):
            value = button_id[len(LANGUAGE_PREFIX) :]
            if value in {lang.value for lang in Language}:
                return Decision(Route.SET_LANGUAGE, language=Language(value))
        if button_id.startswith(SLOT_PREFIX) and button_id[len(SLOT_PREFIX) :].isdigit():
            return Decision(Route.BOOK_SLOT, slot_id=int(button_id[len(SLOT_PREFIX) :]))
        if decision := _counselor(button_id):
            return decision
    if text is not None and normalise(text) in STOP_PHRASES:
        return Decision(Route.OPT_OUT)
    return Decision(Route.LLM)


def _counselor(button_id: str) -> Decision | None:
    parts = button_id.split(":")
    if len(parts) == 3 and parts[0] + ":" == COUNSELOR_PREFIX and parts[1].isdigit():
        event = COUNSELOR_EVENTS.get(parts[2])
        if event:
            return Decision(Route.COUNSELOR_STATUS, lead_id=int(parts[1]), event=event)
    return None
