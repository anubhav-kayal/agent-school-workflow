from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KbFact, Lead, School, VisitSlot
from app.models.enums import Actor, BookingStatus, LeadSource, LeadStatus
from app.services.kb import kb_prompt_block, verified_facts
from app.services.visits import SlotUnavailableError, book_visit, open_slots

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)


async def setup(db: AsyncSession) -> tuple[School, Lead, list[VisitSlot]]:
    s = School(name="Demo", slug="demo-visits", city="Pune")
    db.add(s)
    await db.flush()
    lead = Lead(school_id=s.id, source=LeadSource.WEBSITE, phone="+919999900005")
    slots = [
        VisitSlot(school_id=s.id, starts_at=NOW + timedelta(days=d), capacity=1) for d in (1, 2)
    ]
    db.add_all([lead, *slots])
    db.add_all(
        [
            KbFact(
                school_id=s.id, topic="fees", key="fees.class_1", value="₹85,000", verified=True
            ),
            KbFact(school_id=s.id, topic="results", key="results.x", value="98%", verified=False),
        ]
    )
    await db.flush()
    return s, lead, slots


async def test_only_verified_facts_returned(db: AsyncSession) -> None:
    s, _, _ = await setup(db)
    assert [f.key for f in await verified_facts(db, s.id)] == ["fees.class_1"]
    assert await verified_facts(db, s.id, "results") == []
    block = kb_prompt_block(await verified_facts(db, s.id))
    assert "₹85,000" in block and "98%" not in block


async def test_booking_fills_slot_and_updates_lead(db: AsyncSession) -> None:
    s, lead, slots = await setup(db)
    await book_visit(db, lead, slots[0].id, Actor.ASSISTANT)
    assert lead.status is LeadStatus.VISIT_BOOKED
    remaining = await open_slots(db, s.id, NOW, NOW + timedelta(days=7))
    assert [x.id for x in remaining] == [slots[1].id]


async def test_full_slot_rejected(db: AsyncSession) -> None:
    s, lead, slots = await setup(db)
    other = Lead(school_id=s.id, source=LeadSource.WEBSITE, phone="+919999900006")
    db.add(other)
    await db.flush()
    await book_visit(db, lead, slots[0].id, Actor.ASSISTANT)
    with pytest.raises(SlotUnavailableError):
        await book_visit(db, other, slots[0].id, Actor.ASSISTANT)


async def test_reschedule_frees_previous_seat(db: AsyncSession) -> None:
    _, lead, slots = await setup(db)
    first = await book_visit(db, lead, slots[0].id, Actor.ASSISTANT)
    await book_visit(db, lead, slots[1].id, Actor.ASSISTANT)
    assert first.status is BookingStatus.CANCELLED
    await db.refresh(slots[0])
    assert slots[0].booked_count == 0
