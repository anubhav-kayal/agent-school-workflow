"""Meta Lead Ads: webhook signature + payload parsing, and fetching the full lead.

Shapes follow Meta's documented leadgen webhook and Lead object (TO VERIFY, see PLAN.md).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

GRAPH_BASE = "https://graph.facebook.com"
LEAD_FIELDS = "id,created_time,field_data,ad_id,adset_id,campaign_id,form_id"


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """X-Hub-Signature-256: 'sha256=' + hex HMAC-SHA256 of the raw body with the app secret."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@dataclass(frozen=True)
class LeadgenEvent:
    leadgen_id: str
    page_id: str
    form_id: str | None = None
    ad_id: str | None = None


def parse_leadgen_webhook(payload: dict[str, Any]) -> list[LeadgenEvent]:
    events: list[LeadgenEvent] = []
    if payload.get("object") != "page":
        return events
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            if change.get("field") != "leadgen" or "leadgen_id" not in value:
                continue
            events.append(
                LeadgenEvent(
                    leadgen_id=str(value["leadgen_id"]),
                    page_id=str(value.get("page_id") or entry.get("id")),
                    form_id=_opt(value.get("form_id")),
                    ad_id=_opt(value.get("ad_id")),
                )
            )
    return events


@dataclass(frozen=True)
class MetaLead:
    id: str
    fields: dict[str, str]  # field_data flattened: name -> first value
    form_id: str | None = None
    ad_id: str | None = None
    adset_id: str | None = None
    campaign_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_graph(cls, data: dict[str, Any]) -> MetaLead:
        fields = {f["name"]: (f.get("values") or [""])[0] for f in data.get("field_data", [])}
        return cls(
            str(data["id"]),
            fields,
            _opt(data.get("form_id")),
            _opt(data.get("ad_id")),
            _opt(data.get("adset_id")),
            _opt(data.get("campaign_id")),
            data,
        )

    def first(self, *needles: str) -> str | None:
        """Value of the first field whose name contains any needle (forms vary per school)."""
        for name, value in self.fields.items():
            if any(n in name.lower() for n in needles) and value:
                return value
        return None


class MetaLeadClient(Protocol):
    async def fetch_lead(self, leadgen_id: str) -> MetaLead: ...


class GraphLeadClient:
    def __init__(self, client: httpx.AsyncClient, token: str, graph_version: str) -> None:
        self._client = client
        self._token = token
        self._version = graph_version

    async def fetch_lead(self, leadgen_id: str) -> MetaLead:
        resp = await self._client.get(
            f"{GRAPH_BASE}/{self._version}/{leadgen_id}",
            params={"fields": LEAD_FIELDS},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return MetaLead.from_graph(resp.json())


def _opt(value: Any) -> str | None:
    return None if value in (None, "") else str(value)
