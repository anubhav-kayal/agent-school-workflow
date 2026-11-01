from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeWhatsAppTransport:
    """Records every payload instead of calling Meta. Used by tests and demo mode."""

    sent: list[dict[str, Any]] = field(default_factory=list)

    async def send(self, payload: dict[str, Any]) -> str:
        self.sent.append(payload)
        return f"wamid.FAKE{len(self.sent):06d}"

    def to(self, phone: str) -> list[dict[str, Any]]:
        return [p for p in self.sent if p["to"] == phone.lstrip("+")]
