import json
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.meta_leads import FakeMetaLeadClient
from app.adapters.meta_leads import MetaLead
from app.config import Settings, get_settings
from app.models.enums import LeadSource
from app.seed import seed
from app.services.intake import ingest_meta_lead
from tests.adapters.test_meta_leads import GRAPH_LEAD, SECRET, WEBHOOK, sign
from tests.webhooks.conftest import RecordingEnqueuer


@pytest.fixture(autouse=True)
def meta_settings(client: httpx.AsyncClient) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, meta_app_secret=SECRET, meta_verify_token="fake-verify"
    )  # type: ignore[call-arg]


async def test_subscription_challenge(client: httpx.AsyncClient) -> None:
    ok = await client.get(
        "/webhooks/meta/leads",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "fake-verify",
            "hub.challenge": "1158201444",
        },
    )
    assert (ok.status_code, ok.text) == (200, "1158201444")
    bad = await client.get(
        "/webhooks/meta/leads",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
    )
    assert bad.status_code == 403


async def test_signed_webhook_enqueues_with_dedupe_id(
    client: httpx.AsyncClient, enqueuer: RecordingEnqueuer
) -> None:
    body = json.dumps(WEBHOOK).encode()
    resp = await client.post(
        "/webhooks/meta/leads", content=body, headers={"X-Hub-Signature-256": sign(body)}
    )
    assert resp.json() == {"queued": 1}
    assert enqueuer.jobs[0][1] == "metalead:444444444"
    unsigned = await client.post("/webhooks/meta/leads", content=body)
    assert unsigned.status_code == 401


async def test_ingest_creates_lead_once(db: AsyncSession) -> None:
    await seed(db, today=date(2026, 11, 2))
    fake = FakeMetaLeadClient({"444444444": MetaLead.from_graph(GRAPH_LEAD)})
    lead = await ingest_meta_lead(db, fake, "000000000000001", "444444444")
    assert lead is not None and lead.source is LeadSource.META_LEAD_AD
    assert (lead.phone, lead.grade_interest, lead.ad_set_external_id) == (
        "+919999900040",
        "Class 1",
        "777",
    )
    again = await ingest_meta_lead(db, fake, "000000000000001", "444444444")
    assert again is not None and again.id == lead.id
    assert fake.fetched == ["444444444"]  # replay did not hit the Graph API again
    assert await ingest_meta_lead(db, fake, "unknown-page", "1") is None
