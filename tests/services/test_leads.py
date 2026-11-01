from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.models import Conversation, Lead, LeadEvent, School
from app.models.enums import LeadEventType, LeadStatus
from app.schemas.lead import LeadCreate
from app.services.leads import create_lead, send_first_response


def payload(**kw: object) -> LeadCreate:
    base = {
        "source": "meta_lead_ad",
        "external_lead_id": "L-100",
        "parent_name": "Priya",
        "phone": "9999900001",
        "grade_interest": "Nursery",
        "consent": True,
        "consent_source": "meta_form:FAKE",
    }
    return LeadCreate.model_validate({**base, **kw})


async def school(db: AsyncSession) -> School:
    s = School(name="Demo School", slug="demo-svc", city="Pune")
    db.add(s)
    await db.flush()
    return s


def wa() -> tuple[WhatsAppAdapter, FakeWhatsAppTransport]:
    t = FakeWhatsAppTransport()
    return WhatsAppAdapter(t, {("enquiry_first_response", "en")}), t


async def test_create_lead_is_idempotent(db: AsyncSession) -> None:
    s = await school(db)
    first = await create_lead(db, s.id, payload())
    again = await create_lead(db, s.id, payload())
    assert first.created and not again.created
    assert again.lead.id == first.lead.id
    assert await db.scalar(select(func.count()).select_from(Lead)) == 1
    assert await db.scalar(select(func.count()).select_from(Conversation)) == 1
    assert first.lead.consent_at is not None


async def test_first_response_is_template_and_records_sla(db: AsyncSession) -> None:
    s = await school(db)
    lead = (await create_lead(db, s.id, payload())).lead
    adapter, transport = wa()
    before = datetime.now(UTC)
    assert await send_first_response(db, lead, adapter) is True
    assert lead.first_response_at is not None and lead.first_response_at >= before
    assert lead.status is LeadStatus.CONTACTED
    [sent] = transport.sent
    assert sent["type"] == "template"
    assert sent["template"]["name"] == "enquiry_first_response"
    events = (await db.scalars(select(LeadEvent.event))).all()
    assert events == [LeadEventType.CREATED, LeadEventType.CONTACTED]


async def test_first_response_never_sent_twice(db: AsyncSession) -> None:
    s = await school(db)
    lead = (await create_lead(db, s.id, payload())).lead
    adapter, transport = wa()
    await send_first_response(db, lead, adapter)
    assert await send_first_response(db, lead, adapter) is False
    assert len(transport.sent) == 1


async def test_first_response_skipped_for_opted_out(db: AsyncSession) -> None:
    s = await school(db)
    lead = (await create_lead(db, s.id, payload())).lead
    lead.opted_out_at = datetime.now(UTC)
    adapter, transport = wa()
    assert await send_first_response(db, lead, adapter) is False
    assert transport.sent == []
