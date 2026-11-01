from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeWhatsAppTransport:
    """Records every payload instead of calling Meta. Used by tests and demo mode."""

    sent: list[dict[str, Any]] = field(default_factory=list)

    async def send(self, payload: dict[str, Any]) -> str:
        self.sent.append(payload)
        return f"wamid.FAKE{uuid.uuid4().hex}"  # unique across restarts, like real ids

    def to(self, phone: str) -> list[dict[str, Any]]:
        return [p for p in self.sent if p["to"] == phone.lstrip("+")]

    def bodies(self, phone: str) -> list[str]:
        """Visible text of every free-form message (plain text or interactive) to a phone."""
        out = []
        for p in self.to(phone):
            if p["type"] == "text":
                out.append(p["text"]["body"])
            elif p["type"] == "interactive":
                out.append(p["interactive"]["body"]["text"])
        return out
