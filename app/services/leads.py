"""Lead intake and the first-contact message (no LLM on this path)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.whatsapp import Recipient, WhatsAppAdapter, WhatsAppPolicyError
from app.models import Conversation, Lead, LeadEvent, Message, School
from app.models.enums import Actor, Direction, Language, LeadEventType, LeadStatus
from app.schemas.lead import LeadCreate
from app.services.templates import QUICK_REPLIES, render

FIRST_TEMPLATE = "enquiry_first_response"


@dataclass(frozen=True)
class IntakeResult:
    lead: Lead
    created: bool


async def create_lead(db: AsyncSession, school_id: int, data: LeadCreate) -> IntakeResult:
    """Insert a lead once. Replayed webhooks with the same external id return the original."""
    values = data.model_dump()
    values["consent_at"] = datetime.now(UTC) if data.consent else None
    stmt = insert(Lead).values(school_id=school_id, **values)
    if data.external_lead_id:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["school_id", "source", "external_lead_id"]
        )
    lead_id = (await db.execute(stmt.returning(Lead.id))).scalar_one_or_none()
    if lead_id is None:  # duplicate delivery
        existing = await db.scalar(
            select(Lead).where(
                Lead.school_id == school_id,
                Lead.source == data.source,
                Lead.external_lead_id == data.external_lead_id,
            )
        )
        assert existing is not None
        return IntakeResult(existing, created=False)
    lead = await db.get_one(Lead, lead_id)
    db.add(Conversation(lead_id=lead.id, school_id=school_id))
    db.add(
        LeadEvent(
            lead_id=lead.id,
            school_id=school_id,
            event=LeadEventType.CREATED,
            actor=Actor.SYSTEM,
            note=f"source={data.source.value}",
        )
    )
    await db.flush()
    return IntakeResult(lead, created=True)


async def get_conversation(db: AsyncSession, lead: Lead) -> Conversation:
    return await db.scalar(select(Conversation).where(Conversation.lead_id == lead.id)) or (
        await _create_conversation(db, lead)
    )


async def _create_conversation(db: AsyncSession, lead: Lead) -> Conversation:
    conv = Conversation(lead_id=lead.id, school_id=lead.school_id)
    db.add(conv)
    await db.flush()
    return conv


def recipient_for(lead: Lead, conv: Conversation) -> Recipient:
    assert lead.phone, "lead has no phone (deleted?)"
    return Recipient(lead.phone, conv.last_inbound_at, lead.opted_out_at)


async def send_first_response(db: AsyncSession, lead: Lead, wa: WhatsAppAdapter) -> bool:
    """Send the approved first-contact template. Idempotent: never sends twice."""
    if lead.first_response_at is not None or lead.phone is None:
        return False
    school = await db.get_one(School, lead.school_id)
    conv = await get_conversation(db, lead)
    language = "hi" if lead.language == Language.HI else "en"
    variables = [lead.parent_name or "Parent", school.name, lead.grade_interest or "admission"]
    try:
        wamid = await wa.send_template(
            recipient_for(lead, conv), FIRST_TEMPLATE, language, variables
        )
    except WhatsAppPolicyError:
        return False
    now = datetime.now(UTC)
    lead.first_response_at = now
    if lead.status == LeadStatus.NEW:
        lead.status = LeadStatus.CONTACTED
    db.add(
        Message(
            conversation_id=conv.id,
            direction=Direction.OUTBOUND,
            kind="template",
            template_name=FIRST_TEMPLATE,
            wa_message_id=wamid,
            status="sent",
            body=render(FIRST_TEMPLATE, language, variables),
            payload={
                "language": language,
                "variables": variables,
                "buttons": QUICK_REPLIES.get((FIRST_TEMPLATE, language), []),
            },
        )
    )
    db.add(
        LeadEvent(
            lead_id=lead.id,
            school_id=lead.school_id,
            event=LeadEventType.CONTACTED,
            actor=Actor.SYSTEM,
            idempotency_key=f"first_response:{lead.id}",
        )
    )
    await db.flush()
    return True
