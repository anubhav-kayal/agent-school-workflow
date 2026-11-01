"""WhatsApp adapter: policy (opt-out, 24-hour window, template approval) + Cloud API payloads.

The policy lives here so no caller can bypass it. The transport (`WhatsAppTransport`) is the
only thing that talks HTTP; the fake transport records payloads instead.
Payload shapes follow the Cloud API messages endpoint (TO VERIFY against current docs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

SERVICE_WINDOW = timedelta(hours=24)
MAX_REPLY_BUTTONS = 3
MAX_BUTTON_TITLE = 20
MAX_LIST_ROWS = 10


class WhatsAppPolicyError(Exception):
    """A send that must never happen. Callers escalate or fall back to a template."""


class OptedOutError(WhatsAppPolicyError):
    pass


class OutsideServiceWindowError(WhatsAppPolicyError):
    pass


class TemplateNotApprovedError(WhatsAppPolicyError):
    pass


@dataclass(frozen=True)
class Recipient:
    phone: str  # E.164
    last_inbound_at: datetime | None = None
    opted_out_at: datetime | None = None

    def in_service_window(self, now: datetime) -> bool:
        return self.last_inbound_at is not None and now - self.last_inbound_at < SERVICE_WINDOW


@dataclass(frozen=True)
class Button:
    id: str
    title: str


class WhatsAppTransport(Protocol):
    async def send(self, payload: dict[str, Any]) -> str:
        """POST the message payload; return the wa_message_id."""
        ...


@dataclass
class WhatsAppAdapter:
    transport: WhatsAppTransport
    approved_templates: set[tuple[str, str]] = field(default_factory=set)  # (name, language)
    clock: Any = field(default=lambda: datetime.now(UTC))

    # --- policy -----------------------------------------------------------------------
    def _check_reachable(self, to: Recipient) -> None:
        if to.opted_out_at is not None:
            raise OptedOutError("recipient opted out")

    def _check_free_form(self, to: Recipient) -> None:
        self._check_reachable(to)
        if not to.in_service_window(self.clock()):
            raise OutsideServiceWindowError("free-form message outside the 24-hour window")

    # --- sends ------------------------------------------------------------------------
    async def send_text(self, to: Recipient, body: str) -> str:
        self._check_free_form(to)
        return await self.transport.send(_envelope(to, "text", {"body": body}))

    async def send_buttons(self, to: Recipient, body: str, buttons: list[Button]) -> str:
        self._check_free_form(to)
        if not 1 <= len(buttons) <= MAX_REPLY_BUTTONS:
            raise ValueError(f"reply buttons must be 1..{MAX_REPLY_BUTTONS}")
        action = {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {"id": b.id, "title": b.title[:MAX_BUTTON_TITLE].rstrip()},
                }
                for b in buttons
            ]
        }
        interactive = {"type": "button", "body": {"text": body}, "action": action}
        return await self.transport.send(_envelope(to, "interactive", interactive))

    async def send_list(
        self, to: Recipient, body: str, button_label: str, rows: list[Button]
    ) -> str:
        self._check_free_form(to)
        if not 1 <= len(rows) <= MAX_LIST_ROWS:
            raise ValueError(f"list rows must be 1..{MAX_LIST_ROWS}")
        section = {
            "title": button_label[:24],
            "rows": [{"id": r.id, "title": r.title[:24]} for r in rows],
        }
        interactive = {
            "type": "list",
            "body": {"text": body},
            "action": {"button": button_label[:MAX_BUTTON_TITLE], "sections": [section]},
        }
        return await self.transport.send(_envelope(to, "interactive", interactive))

    async def send_template(
        self, to: Recipient, name: str, language: str, variables: list[str]
    ) -> str:
        """Business-initiated message; allowed outside the window, never after opt-out."""
        self._check_reachable(to)
        if (name, language) not in self.approved_templates:
            raise TemplateNotApprovedError(f"template {name}/{language} is not approved")
        template = {
            "name": name,
            "language": {"code": language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": v} for v in variables]}
            ],
        }
        return await self.transport.send(_envelope(to, "template", template))


def _envelope(to: Recipient, kind: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.phone.lstrip("+"),
        "type": kind,
        kind: content,
    }
