import json
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.adapters.whatsapp_inbound import parse_whatsapp_webhook
from app.agents.llm.fake import ScriptedProvider, text_turn
from app.config import Settings, get_settings
from app.models import Lead, Message
from app.models.enums import LeadSource, LeadStatus
from app.seed import seed
from app.services.conversation import Deps
from app.services.inbound_whatsapp import process_whatsapp_message
from tests.adapters.test_meta_leads import SECRET, sign
from tests.adapters.test_whatsapp_inbound import QUICK, STATUS, TEXT
from tests.webhooks.conftest import RecordingEnqueuer


@pytest.fixture(autouse=True)
def wa_settings(client: httpx.AsyncClient) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, whatsapp_app_secret=SECRET
    )  # type: ignore[call-arg]


# Sample payload timestamps are fixed; pin the adapter clock just after them so the
# 24-hour window check sees a fresh inbound message.
CLOCK = datetime.fromtimestamp(1762056000 + 60, tz=UTC)


def deps(*turns: object) -> tuple[Deps, FakeWhatsAppTransport]:
    t = FakeWhatsAppTransport()
    adapter = WhatsAppAdapter(t, {("counselor_lead_alert", "en")}, clock=lambda: CLOCK)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    return Deps(settings, ScriptedProvider(list(turns)), adapter), t  # type: ignore[arg-type]


async def test_webhook_queues_messages_and_needs_signature(
    client: httpx.AsyncClient, enqueuer: RecordingEnqueuer
) -> None:
    body = json.dumps(TEXT).encode()
    resp = await client.post(
        "/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": sign(body)}
    )
    assert resp.json() == {"messages": 1, "statuses": 0}
    job, job_id, kwargs = enqueuer.jobs[0]
    assert (job, job_id, kwargs["text"]) == (
        "process_whatsapp_message",
        "wa:wamid.T1",
        "fees kitni hai?",
    )
    assert (await client.post("/webhooks/whatsapp", content=body)).status_code == 401


async def test_status_updates_applied_inline(db: AsyncSession, client: httpx.AsyncClient) -> None:
    await seed(db, today=date(2026, 11, 2))
    body = json.dumps(STATUS).encode()
    resp = await client.post(
        "/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": sign(body)}
    )
    assert resp.json()["statuses"] == 1


async def test_unknown_parent_becomes_whatsapp_lead_and_gets_reply(db: AsyncSession) -> None:
    await seed(db, today=date(2026, 11, 2))
    d, transport = deps(text_turn("Ji, Class 1 ki fees ₹85,000 per year hai."))
    [msg], _ = parse_whatsapp_webhook(TEXT)
    assert await process_whatsapp_message(db, d, msg) == "llm"
    lead = await db.scalar(select(Lead).where(Lead.phone == "+919999900050"))
    assert lead is not None and lead.source is LeadSource.WHATSAPP
    assert lead.consent_source == "whatsapp_inbound" and lead.first_response_at is not None
    assert transport.bodies("+919999900050")[0].startswith("Ji, Class 1")
    assert await db.scalar(select(Message.id).where(Message.wa_message_id == "wamid.T1"))


async def test_counselor_quick_reply_updates_lead(db: AsyncSession) -> None:
    await seed(db, today=date(2026, 11, 2))
    from app.models import School

    school = await db.scalar(select(School))
    assert school
    lead = Lead(school_id=school.id, source=LeadSource.WEBSITE, phone="+919999900051")
    db.add(lead)
    await db.flush()
    payload = json.loads(json.dumps(QUICK).replace("lead:5:", f"lead:{lead.id}:"))
    [msg], _ = parse_whatsapp_webhook(payload)
    d, _ = deps()
    assert await process_whatsapp_message(db, d, msg) == "counselor_status"
    assert lead.status is LeadStatus.VISITED
