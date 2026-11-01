"""Visit slots and bookings. Capacity is enforced atomically in SQL."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, LeadEvent, VisitBooking, VisitSlot
from app.models.enums import Actor, BookingStatus, LeadEventType, LeadStatus


class SlotUnavailableError(Exception):
    pass


async def open_slots(
    db: AsyncSession, school_id: int, after: datetime, before: datetime, limit: int = 10
) -> list[VisitSlot]:
    stmt = (
        select(VisitSlot)
        .where(
            VisitSlot.school_id == school_id,
            VisitSlot.starts_at > after,
            VisitSlot.starts_at < before,
            VisitSlot.booked_count < VisitSlot.capacity,
        )
        .order_by(VisitSlot.starts_at)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def active_booking(db: AsyncSession, lead_id: int) -> VisitBooking | None:
    return await db.scalar(
        select(VisitBooking).where(
            VisitBooking.lead_id == lead_id, VisitBooking.status == BookingStatus.BOOKED
        )
    )


async def book_visit(db: AsyncSession, lead: Lead, slot_id: int, actor: Actor) -> VisitBooking:
    """Book (or move) the lead's visit. Raises SlotUnavailableError if full or foreign."""
    taken = await db.execute(
        update(VisitSlot)
        .where(
            VisitSlot.id == slot_id,
            VisitSlot.school_id == lead.school_id,
            VisitSlot.booked_count < VisitSlot.capacity,
        )
        .values(booked_count=VisitSlot.booked_count + 1)
        .returning(VisitSlot.id)
    )
    if taken.scalar_one_or_none() is None:
        raise SlotUnavailableError(f"slot {slot_id} is full or unknown")
    previous = await active_booking(db, lead.id)
    if previous is not None:  # reschedule: free the old seat
        previous.status = BookingStatus.CANCELLED
        await db.execute(
            update(VisitSlot)
            .where(VisitSlot.id == previous.slot_id)
            .values(booked_count=VisitSlot.booked_count - 1)
        )
    booking = VisitBooking(lead_id=lead.id, slot_id=slot_id)
    db.add(booking)
    lead.status = LeadStatus.VISIT_BOOKED
    db.add(
        LeadEvent(
            lead_id=lead.id,
            school_id=lead.school_id,
            event=LeadEventType.VISIT_BOOKED,
            actor=actor,
            note=f"slot={slot_id}",
        )
    )
    await db.flush()
    return booking
