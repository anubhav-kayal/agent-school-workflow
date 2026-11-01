"""Visit reminders: day-before (18:00 IST) and morning-of (08:00 IST or 2 h before)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.whatsapp import WhatsAppAdapter, WhatsAppPolicyError
from app.formatting import IST, format_slot, to_ist
from app.models import Lead, Message, School, VisitBooking, VisitSlot
from app.models.enums import BookingStatus, Direction, Language
from app.services.leads import get_conversation, recipient_for
from app.services.templates import render

DAY_BEFORE = "visit_reminder_day_before"
MORNING = "visit_reminder_morning"


def day_before_due(starts_at: datetime, now: datetime) -> bool:
    local_day = to_ist(starts_at).date()
    send_at = datetime.combine(local_day - timedelta(days=1), time(18, 0), tzinfo=IST)
    return send_at <= now < starts_at - timedelta(hours=6)


def morning_due(starts_at: datetime, now: datetime) -> bool:
    eight = datetime.combine(to_ist(starts_at).date(), time(8, 0), tzinfo=IST)
    return max(eight, starts_at - timedelta(hours=2)) <= now < starts_at


async def send_due_reminders(db: AsyncSession, wa: WhatsAppAdapter, now: datetime) -> int:
    rows = (
        await db.execute(
            select(VisitBooking, VisitSlot, Lead, School)
            .join(VisitSlot, VisitSlot.id == VisitBooking.slot_id)
            .join(Lead, Lead.id == VisitBooking.lead_id)
            .join(School, School.id == Lead.school_id)
            .where(
                VisitBooking.status == BookingStatus.BOOKED,
                VisitSlot.starts_at > now,
                VisitSlot.starts_at < now + timedelta(days=2),
                Lead.opted_out_at.is_(None),
                Lead.deleted_at.is_(None),
            )
        )
    ).all()
    sent = 0
    for booking, slot, lead, school in rows:
        template = _due_template(booking, slot.starts_at, now)
        if template and await _send(db, wa, lead, school, slot, template):
            if template == DAY_BEFORE:
                booking.reminder_day_before_sent_at = now
            else:
                booking.reminder_morning_sent_at = now
            sent += 1
    await db.flush()
    return sent


def _due_template(booking: VisitBooking, starts_at: datetime, now: datetime) -> str | None:
    if booking.reminder_day_before_sent_at is None and day_before_due(starts_at, now):
        return DAY_BEFORE
    if booking.reminder_morning_sent_at is None and morning_due(starts_at, now):
        return MORNING
    return None


async def _send(
    db: AsyncSession,
    wa: WhatsAppAdapter,
    lead: Lead,
    school: School,
    slot: VisitSlot,
    template: str,
) -> bool:
    lang = "hi" if lead.language == Language.HI else "en"
    clock = format_slot(slot.starts_at, lang).split(", ")[-1]
    name = lead.parent_name or "Parent"
    address = "the school campus"
    variables = (
        [name, school.name, clock]
        if template == DAY_BEFORE
        else [name, clock, school.name, address]
    )
    conv = await get_conversation(db, lead)
    try:
        wamid = await wa.send_template(recipient_for(lead, conv), template, lang, variables)
    except WhatsAppPolicyError:
        return False
    db.add(
        Message(
            conversation_id=conv.id,
            direction=Direction.OUTBOUND,
            kind="template",
            template_name=template,
            body=render(template, lang, variables),
            wa_message_id=wamid,
            status="sent",
        )
    )
    return True
