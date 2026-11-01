from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.models import Lead, School, VisitSlot
from app.models.enums import Actor, LeadSource
from app.services.reminders import day_before_due, morning_due, send_due_reminders
from app.services.templates import ALL_TEMPLATE_KEYS
from app.services.visits import book_visit

SLOT = datetime(2026, 11, 7, 4, 30, tzinfo=UTC)  # Sat 10:00 IST
IST_6PM_FRI = datetime(2026, 11, 6, 12, 30, tzinfo=UTC)
IST_8AM_SAT = datetime(2026, 11, 7, 2, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "day_before", "morning"),
    [
        (IST_6PM_FRI - timedelta(minutes=1), False, False),
        (IST_6PM_FRI, True, False),
        (IST_8AM_SAT, False, True),
        (SLOT, False, False),
    ],
)
def test_due_windows(now: datetime, day_before: bool, morning: bool) -> None:
    assert day_before_due(SLOT, now) is day_before
    assert morning_due(SLOT, now) is morning


async def booked_lead(db: AsyncSession, opted_out: bool = False) -> Lead:
    school = School(name="Demo", slug="demo-rem", city="Pune")
    db.add(school)
    await db.flush()
    lead = Lead(
        school_id=school.id,
        source=LeadSource.WEBSITE,
        phone="+919999900060",
        parent_name="Test",
        opted_out_at=IST_6PM_FRI - timedelta(days=1) if opted_out else None,
    )
    slot = VisitSlot(school_id=school.id, starts_at=SLOT, capacity=3)
    db.add_all([lead, slot])
    await db.flush()
    await book_visit(db, lead, slot.id, Actor.ASSISTANT)
    return lead


async def test_reminders_sent_once_each(db: AsyncSession) -> None:
    await booked_lead(db)
    transport = FakeWhatsAppTransport()
    wa = WhatsAppAdapter(transport, set(ALL_TEMPLATE_KEYS))
    assert await send_due_reminders(db, wa, IST_6PM_FRI) == 1
    assert await send_due_reminders(db, wa, IST_6PM_FRI + timedelta(minutes=15)) == 0
    assert await send_due_reminders(db, wa, IST_8AM_SAT) == 1
    names = [p["template"]["name"] for p in transport.sent]
    assert names == ["visit_reminder_day_before", "visit_reminder_morning"]


async def test_no_reminders_after_opt_out(db: AsyncSession) -> None:
    await booked_lead(db, opted_out=True)
    transport = FakeWhatsAppTransport()
    wa = WhatsAppAdapter(transport, set(ALL_TEMPLATE_KEYS))
    for now in (IST_6PM_FRI, IST_8AM_SAT):
        assert await send_due_reminders(db, wa, now) == 0
    assert transport.sent == []
