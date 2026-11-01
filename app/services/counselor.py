"""Counselor hand-off: alert with status buttons, and status updates from button taps."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.whatsapp import Recipient, WhatsAppAdapter, WhatsAppPolicyError
from app.models import Lead, LeadEvent, User, VisitBooking
from app.models.enums import Actor, BookingStatus, LeadEventType, LeadStatus, UserRole

ALERT_TEMPLATE = "counselor_lead_alert"
STATUS_BUTTONS = ["visit_booked", "visited", "admitted", "not_interested"]
EVENT_TO_STATUS = {
    LeadEventType.VISIT_BOOKED: LeadStatus.VISIT_BOOKED,
    LeadEventType.VISITED: LeadStatus.VISITED,
    LeadEventType.ADMITTED: LeadStatus.ADMITTED,
    LeadEventType.NOT_INTERESTED: LeadStatus.NOT_INTERESTED,
}


async def counselors(db: AsyncSession, school_id: int) -> list[User]:
    stmt = select(User).where(
        User.school_id == school_id,
        User.role == UserRole.COUNSELOR,
        User.is_active.is_(True),
        User.whatsapp_number.is_not(None),
    )
    return list((await db.scalars(stmt)).all())


def status_payloads(lead_id: int) -> list[str]:
    return [f"lead:{lead_id}:{event}" for event in STATUS_BUTTONS]


async def alert_counselors(
    db: AsyncSession, wa: WhatsAppAdapter, lead: Lead, reason: str, last_message: str
) -> int:
    """Send the alert template to every active counselor. Returns how many were sent."""
    variables = [
        f"#{lead.id}",
        lead.parent_name or "Parent",
        lead.grade_interest or "-",
        reason[:120],
        last_message[:200],
    ]
    sent = 0
    for user in await counselors(db, lead.school_id):
        assert user.whatsapp_number
        try:
            await wa.send_template(
                Recipient(user.whatsapp_number),
                ALERT_TEMPLATE,
                "en",
                variables,
                status_payloads(lead.id),
            )
            sent += 1
        except WhatsAppPolicyError:
            continue
    return sent


async def apply_counselor_status(
    db: AsyncSession,
    counselor_phone: str,
    lead_id: int,
    event: LeadEventType,
    idempotency_key: str,
) -> LeadEvent | None:
    """Record a counselor's button tap. Ignores strangers and replays."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        return None
    allowed = {u.whatsapp_number for u in await counselors(db, lead.school_id)}
    if counselor_phone not in allowed:
        return None
    if await db.scalar(select(LeadEvent).where(LeadEvent.idempotency_key == idempotency_key)):
        return None
    lead.status = EVENT_TO_STATUS[event]
    if event == LeadEventType.VISITED:
        booking = await db.scalar(
            select(VisitBooking).where(
                VisitBooking.lead_id == lead.id, VisitBooking.status == BookingStatus.BOOKED
            )
        )
        if booking:
            booking.status = BookingStatus.ATTENDED
    lead_event = LeadEvent(
        lead_id=lead.id,
        school_id=lead.school_id,
        event=event,
        actor=Actor.COUNSELOR,
        idempotency_key=idempotency_key,
    )
    db.add(lead_event)
    await db.flush()
    return lead_event
