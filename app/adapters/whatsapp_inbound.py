"""Parse WhatsApp Cloud API webhook payloads (messages + statuses). TO VERIFY shapes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    phone_number_id: str  # our business number (routes to a school)
    sender: str  # E.164
    wa_message_id: str
    sent_at: datetime
    text: str | None
    button_id: str | None  # interactive reply id or template quick-reply payload


@dataclass(frozen=True)
class StatusUpdate:
    wa_message_id: str
    status: str  # sent | delivered | read | failed


def parse_whatsapp_webhook(
    payload: dict[str, Any],
) -> tuple[list[InboundMessage], list[StatusUpdate]]:
    messages: list[InboundMessage] = []
    statuses: list[StatusUpdate] = []
    if payload.get("object") != "whatsapp_business_account":
        return messages, statuses
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            number_id = str((value.get("metadata") or {}).get("phone_number_id", ""))
            for m in value.get("messages", []):
                parsed = _message(number_id, m)
                if parsed:
                    messages.append(parsed)
            for s in value.get("statuses", []):
                statuses.append(StatusUpdate(str(s["id"]), str(s.get("status", ""))))
    return messages, statuses


def _message(number_id: str, m: dict[str, Any]) -> InboundMessage | None:
    kind = m.get("type")
    text = button_id = None
    if kind == "text":
        text = (m.get("text") or {}).get("body")
    elif kind == "interactive":
        reply = m.get("interactive") or {}
        chosen = reply.get("button_reply") or reply.get("list_reply") or {}
        button_id, text = chosen.get("id"), chosen.get("title")
    elif kind == "button":  # quick reply on a template
        button_id, text = (
            (m.get("button") or {}).get("payload"),
            (m.get("button") or {}).get("text"),
        )
    else:
        return None  # media, location, reactions: ignored in v1 (counselor sees nothing)
    sent_at = datetime.fromtimestamp(int(m.get("timestamp", 0)), tz=UTC)
    return InboundMessage(
        number_id, "+" + str(m["from"]).lstrip("+"), str(m["id"]), sent_at, text, button_id
    )
