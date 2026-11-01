"""Route one inbound WhatsApp message: counselor status tap, or parent conversation."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.whatsapp_inbound import InboundMessage, StatusUpdate
from app.models import Lead, Message, School
from app.models.enums import LeadSource
from app.schemas.lead import LeadCreate
from app.services import counselor
from app.services.conversation import Deps, handle_parent_message
from app.services.leads import create_lead
from app.services.routing import Route, route_inbound


async def process_whatsapp_message(db: AsyncSession, deps: Deps, msg: InboundMessage) -> str:
    school = await db.scalar(
        select(School).where(School.whatsapp_phone_number_id == msg.phone_number_id)
    )
    if school is None:
        return "unknown_number"
    staff = {u.whatsapp_number for u in await counselor.counselors(db, school.id)}
    if msg.sender in staff:
        decision = route_inbound(msg.text, msg.button_id)
        if decision.route is Route.COUNSELOR_STATUS and decision.lead_id and decision.event:
            await counselor.apply_counselor_status(
                db, msg.sender, decision.lead_id, decision.event, msg.wa_message_id
            )
            return "counselor_status"
        return "counselor_ignored"
    lead = await db.scalar(
        select(Lead)
        .where(Lead.school_id == school.id, Lead.phone == msg.sender, Lead.deleted_at.is_(None))
        .order_by(Lead.id.desc())
        .limit(1)
    )
    if lead is None:  # parent wrote to us first (click-to-WhatsApp ad, website button)
        data = LeadCreate(
            source=LeadSource.WHATSAPP,
            phone=msg.sender,
            consent=True,
            consent_source="whatsapp_inbound",
        )
        lead = (await create_lead(db, school.id, data)).lead
        if lead.first_response_at is None:
            lead.first_response_at = msg.sent_at  # the assistant replies within this job
    outcome = await handle_parent_message(
        db, deps, lead, msg.text, msg.button_id, msg.wa_message_id, msg.sent_at
    )
    return outcome.route


async def apply_status(db: AsyncSession, status: StatusUpdate) -> None:
    await db.execute(
        update(Message)
        .where(Message.wa_message_id == status.wa_message_id)
        .values(status=status.status)
    )
