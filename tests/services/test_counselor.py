from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.models import Lead, School
from app.models.enums import LeadEventType, LeadSource, LeadStatus
from app.seed import SLUG, seed
from app.services.counselor import alert_counselors, apply_counselor_status

COUNSELOR = "+919999900102"  # seeded fake counselor


async def lead(db: AsyncSession) -> Lead:
    await seed(db, today=date(2026, 11, 2))
    school = await db.scalar(select(School).where(School.slug == SLUG))
    assert school
    lead = Lead(
        school_id=school.id,
        source=LeadSource.WEBSITE,
        phone="+919999900011",
        parent_name="Test Parent",
        grade_interest="Class 1",
    )
    db.add(lead)
    await db.flush()
    return lead


async def test_alert_sends_template_with_four_status_buttons(db: AsyncSession) -> None:
    ld = await lead(db)
    transport = FakeWhatsAppTransport()
    wa = WhatsAppAdapter(transport, {("counselor_lead_alert", "en")})
    assert await alert_counselors(db, wa, ld, "Asked about results", "results?") == 1
    [sent] = transport.sent
    assert sent["to"] == COUNSELOR.lstrip("+")
    buttons = [c for c in sent["template"]["components"] if c["type"] == "button"]
    payloads = [b["parameters"][0]["payload"] for b in buttons]
    assert payloads == [
        f"lead:{ld.id}:{e}" for e in ("visit_booked", "visited", "admitted", "not_interested")
    ]


async def test_counselor_tap_creates_event_once(db: AsyncSession) -> None:
    ld = await lead(db)
    ev = await apply_counselor_status(db, COUNSELOR, ld.id, LeadEventType.VISITED, "wamid.T1")
    assert ev is not None and ld.status is LeadStatus.VISITED
    replay = await apply_counselor_status(db, COUNSELOR, ld.id, LeadEventType.VISITED, "wamid.T1")
    assert replay is None


async def test_unknown_number_cannot_change_status(db: AsyncSession) -> None:
    ld = await lead(db)
    ev = await apply_counselor_status(db, "+919999900999", ld.id, LeadEventType.ADMITTED, "w2")
    assert ev is None and ld.status is LeadStatus.NEW
