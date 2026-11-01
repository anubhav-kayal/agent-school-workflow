"""DPDP Act: erase a lead's personal data on request (admin action).

Personal fields and message text are scrubbed; anonymous funnel events stay so school-level
counts (leads, visits, admissions) remain correct. The phone is also opted out for safety.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Conversation, Lead, Message, VisitBooking, VisitSlot
from app.models.enums import BookingStatus


async def erase_lead(db: AsyncSession, lead_id: int, actor: str, now: datetime) -> bool:
    lead = await db.get(Lead, lead_id)
    if lead is None or lead.deleted_at is not None:
        return False
    lead.parent_name = lead.phone = lead.email = lead.gclid = None
    lead.deleted_at = now
    lead.opted_out_at = lead.opted_out_at or now
    conv_ids = select(Conversation.id).where(Conversation.lead_id == lead.id)
    await db.execute(
        update(Message).where(Message.conversation_id.in_(conv_ids)).values(body=None, payload={})
    )
    bookings = (
        await db.scalars(
            select(VisitBooking).where(
                VisitBooking.lead_id == lead.id, VisitBooking.status == BookingStatus.BOOKED
            )
        )
    ).all()
    for booking in bookings:  # free the seat
        booking.status = BookingStatus.CANCELLED
        await db.execute(
            update(VisitSlot)
            .where(VisitSlot.id == booking.slot_id)
            .values(booked_count=VisitSlot.booked_count - 1)
        )
    db.add(
        AuditLog(
            school_id=lead.school_id,
            actor=actor,
            action="erase_lead_pii",
            target=f"lead:{lead.id}",
            before=None,
            after={"deleted_at": now.isoformat()},
            dry_run=False,
        )
    )
    await db.flush()
    return True
