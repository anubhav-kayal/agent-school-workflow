from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, LeadEvent, School, VisitSlot
from app.models.enums import Actor, LeadEventType, LeadSource, LeadStatus

NOW = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)


async def make_school(db: AsyncSession) -> School:
    school = School(name="Demo", slug="demo-leads", city="Pune")
    db.add(school)
    await db.flush()
    return school


def meta_lead(school_id: int, external_id: str = "L-1") -> Lead:
    return Lead(
        school_id=school_id,
        source=LeadSource.META_LEAD_AD,
        external_lead_id=external_id,
        parent_name="Test Parent",
        phone="+919999900001",
        consent=True,
    )


async def test_lead_defaults(db: AsyncSession) -> None:
    school = await make_school(db)
    lead = meta_lead(school.id)
    db.add(lead)
    await db.flush()
    assert lead.status is LeadStatus.NEW
    assert lead.opted_out_at is None


async def test_duplicate_external_lead_rejected(db: AsyncSession) -> None:
    school = await make_school(db)
    db.add_all([meta_lead(school.id), meta_lead(school.id)])
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_leads_without_external_id_are_allowed(db: AsyncSession) -> None:
    school = await make_school(db)
    for _ in range(2):
        db.add(Lead(school_id=school.id, source=LeadSource.WEBSITE, phone="+919999900002"))
    await db.flush()


async def test_lead_event_idempotency_key_unique(db: AsyncSession) -> None:
    school = await make_school(db)
    lead = meta_lead(school.id)
    db.add(lead)
    await db.flush()
    for _ in range(2):
        db.add(
            LeadEvent(
                lead_id=lead.id,
                school_id=school.id,
                event=LeadEventType.VISITED,
                actor=Actor.COUNSELOR,
                idempotency_key="wamid.FAKE1",
                created_at=NOW,
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_slot_cannot_be_overbooked(db: AsyncSession) -> None:
    school = await make_school(db)
    db.add(VisitSlot(school_id=school.id, starts_at=NOW, capacity=2, booked_count=3))
    with pytest.raises(IntegrityError):
        await db.flush()
