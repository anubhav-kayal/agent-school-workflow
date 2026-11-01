"""Lead in → template → fees question (KB answer) → slot booked → counselor alert →
counselor taps "Visited" → lead_event stored and pending conversion sync.

Everything goes through the real webhook endpoints and worker jobs; only external APIs and
the model are faked.
"""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm.fake import text_turn, tool_turn
from app.config import Settings, get_settings
from app.jobs import worker
from app.models import Lead, LeadEvent, VisitSlot
from app.models.enums import LeadEventType, LeadStatus
from tests.adapters.test_meta_leads import SECRET, WEBHOOK, sign
from tests.jobs.test_worker import ctx_for
from tests.webhooks.conftest import RecordingEnqueuer

PARENT, COUNSELOR = "919999900040", "919999900102"


@pytest.fixture(autouse=True)
def signed_settings(client: httpx.AsyncClient) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, meta_app_secret=SECRET, whatsapp_app_secret=SECRET
    )  # type: ignore[call-arg]


async def post_signed(client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode()
    resp = await client.post(path, content=body, headers={"X-Hub-Signature-256": sign(body)})
    assert resp.status_code == 200, resp.text


def wa_message(sender: str, wamid: str, **content: Any) -> dict[str, Any]:
    message = {
        "from": sender,
        "id": wamid,
        "timestamp": str(int(datetime.now(UTC).timestamp())),
        **content,
    }
    value = {"metadata": {"phone_number_id": "000000000000002"}, "messages": [message]}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": value}]}],
    }


async def run_jobs(ctx: dict[str, Any], enqueuer: RecordingEnqueuer) -> None:
    jobs, enqueuer.jobs = enqueuer.jobs, []
    for name, _job_id, kwargs in jobs:
        await getattr(worker, name)(ctx, **kwargs)


async def test_lead_to_visit_end_to_end(
    db: AsyncSession, client: httpx.AsyncClient, enqueuer: RecordingEnqueuer
) -> None:
    ctx = await ctx_for(
        db,
        tool_turn("get_school_facts", topic="fees"),
        text_turn(
            "Class 1 fees are ₹85,000 per year, payable in 4 instalments. Would you like "
            "to visit the campus?"
        ),
    )
    sent = ctx["wa"].transport.sent

    await post_signed(client, "/webhooks/meta/leads", WEBHOOK)  # 1. lead in
    await run_jobs(ctx, enqueuer)
    lead = await db.scalar(select(Lead).where(Lead.external_lead_id == "444444444"))
    assert lead is not None and lead.first_response_at is not None
    assert sent[-1]["type"] == "template"  # 2. template, no LLM

    await post_signed(
        client,
        "/webhooks/whatsapp",  # 3. fees question
        wa_message(
            PARENT, "wamid.P1", type="text", text={"body": "What are the fees for class 1?"}
        ),
    )
    await run_jobs(ctx, enqueuer)
    assert "₹85,000" in ctx["wa"].transport.bodies("+" + PARENT)[-1]  # 4. KB answer

    slot = await db.scalar(select(VisitSlot).order_by(VisitSlot.starts_at))
    assert slot is not None
    await post_signed(
        client,
        "/webhooks/whatsapp",
        wa_message(  # 5. books a slot
            PARENT,
            "wamid.P2",
            type="interactive",
            interactive={
                "type": "button_reply",
                "button_reply": {"id": f"slot:{slot.id}", "title": "Sat"},
            },
        ),
    )
    await run_jobs(ctx, enqueuer)
    assert lead.status is LeadStatus.VISIT_BOOKED
    alert = next(p for p in sent if p["to"] == COUNSELOR)  # 6. counselor alert
    assert alert["template"]["name"] == "counselor_lead_alert"

    await post_signed(
        client,
        "/webhooks/whatsapp",
        wa_message(  # 7. taps "Visited"
            COUNSELOR,
            "wamid.C1",
            type="button",
            button={"payload": f"lead:{lead.id}:visited", "text": "Visited"},
        ),
    )
    await run_jobs(ctx, enqueuer)
    visited = await db.scalar(
        select(LeadEvent).where(
            LeadEvent.lead_id == lead.id, LeadEvent.event == LeadEventType.VISITED
        )
    )
    assert visited is not None and lead.status is LeadStatus.VISITED  # 8. event stored
    assert visited.synced_to_meta_at is None  # 9. pending: the M7 CAPI outbox picks these up
