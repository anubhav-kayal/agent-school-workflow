from __future__ import annotations

from dataclasses import dataclass, field

from app.adapters.meta_leads import MetaLead


@dataclass
class FakeMetaLeadClient:
    leads: dict[str, MetaLead] = field(default_factory=dict)
    fetched: list[str] = field(default_factory=list)

    async def fetch_lead(self, leadgen_id: str) -> MetaLead:
        self.fetched.append(leadgen_id)
        return self.leads[leadgen_id]
