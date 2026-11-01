from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Conversation, Lead, LeadEvent, Message, School, VisitSlot
from app.models.enums import Actor, Direction, LeadSource
from app.services.privacy import erase_lead
from app.services.visits import book_visit

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)


async def test_erase_scrubs_pii_frees_seat_keeps_funnel(db: AsyncSession) -> None:
    school = School(name="Demo", slug="demo-privacy", city="Pune")
    db.add(school)
    await db.flush()
    lead = Lead(
        school_id=school.id,
        source=LeadSource.WEBSITE,
        phone="+919999900080",
        parent_name="Test Parent",
        email="parent@example.test",
    )
    slot = VisitSlot(school_id=school.id, starts_at=NOW + timedelta(days=1), capacity=2)
    db.add_all([lead, slot])
    await db.flush()
    conv = Conversation(lead_id=lead.id, school_id=school.id)
    db.add(conv)
    await db.flush()
    db.add(
        Message(
            conversation_id=conv.id,
            direction=Direction.INBOUND,
            kind="text",
            body="My son's name is ...",
        )
    )
    await book_visit(db, lead, slot.id, Actor.ASSISTANT)

    assert await erase_lead(db, lead.id, "admin:dpo@example.test", NOW) is True
    await db.refresh(slot)
    assert (lead.parent_name, lead.phone, lead.email) == (None, None, None)
    assert lead.deleted_at == NOW and lead.opted_out_at == NOW
    assert await db.scalar(select(Message.body)) is None
    assert slot.booked_count == 0
    assert await db.scalar(select(func.count()).select_from(LeadEvent)) == 1  # funnel kept
    audit = await db.scalar(select(AuditLog))
    assert audit is not None and audit.action == "erase_lead_pii"
    assert await erase_lead(db, lead.id, "admin:x", NOW) is False  # idempotent
