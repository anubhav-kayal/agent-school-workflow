"""One inbound parent message → deterministic route or assistant reply → WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.whatsapp import Button, WhatsAppAdapter
from app.agents.assistant import run_assistant
from app.agents.llm import LLMProvider
from app.config import Settings
from app.formatting import format_slot
from app.models import Conversation, Lead, Message, VisitSlot
from app.models.enums import Actor, Direction, Language
from app.services import counselor, visits
from app.services.leads import get_conversation, recipient_for
from app.services.routing import Route, route_inbound

BOOKED_TEXT = {
    "en": "Your campus visit is booked for {slot}. We look forward to meeting you!",
    "hi": "आपकी कैंपस विज़िट {slot} के लिए बुक हो गई है। हमें आपसे मिलने का इंतज़ार रहेगा!",
    "hinglish": "Aapki campus visit {slot} ke liye book ho gayi hai. Milte hain!",
}


@dataclass
class Deps:
    settings: Settings
    provider: LLMProvider
    wa: WhatsAppAdapter


@dataclass
class Outcome:
    route: str
    reply: str | None = None
    buttons: list[Button] = field(default_factory=list)
    escalated: bool = False


async def handle_parent_message(
    db: AsyncSession,
    deps: Deps,
    lead: Lead,
    text: str | None,
    button_id: str | None,
    wa_message_id: str | None,
    now: datetime,
) -> Outcome:
    if wa_message_id and await db.scalar(
        select(Message.id).where(Message.wa_message_id == wa_message_id)
    ):
        return Outcome("duplicate")
    conv = await get_conversation(db, lead)
    db.add(
        Message(
            conversation_id=conv.id,
            direction=Direction.INBOUND,
            kind="button_reply" if button_id else "text",
            body=text,
            wa_message_id=wa_message_id,
            status="received",
            payload={"button_id": button_id} if button_id else {},
        )
    )
    conv.last_inbound_at = now
    await db.flush()
    if lead.opted_out_at is not None:
        return Outcome("opted_out")  # never message an opted-out number again
    decision = route_inbound(text, button_id)
    if decision.route is Route.OPT_OUT:
        lead.opted_out_at = now
        await db.flush()
        return Outcome("opt_out")
    if decision.route is Route.BOOK_SLOT and decision.slot_id is not None:
        try:
            await visits.book_visit(db, lead, decision.slot_id, Actor.ASSISTANT)
        except visits.SlotUnavailableError:
            pass  # let the assistant offer other slots
        else:
            return await _confirm_booking(db, deps, lead, conv, decision.slot_id)
    return await _assistant_turn(db, deps, lead, conv, text or "", now)


async def _confirm_booking(
    db: AsyncSession, deps: Deps, lead: Lead, conv: Conversation, slot_id: int
) -> Outcome:
    slot = await db.get_one(VisitSlot, slot_id)
    lang = lead.language.value if lead.language != Language.EN else "en"
    label = format_slot(slot.starts_at, "hi" if lang == "hi" else "en")
    text = BOOKED_TEXT[lang].format(slot=label)
    await send_and_record(db, deps.wa, lead, conv, text, [])
    await counselor.alert_counselors(db, deps.wa, lead, f"Visit booked: {label}", text)
    return Outcome("book_slot", text)


async def _assistant_turn(
    db: AsyncSession, deps: Deps, lead: Lead, conv: Conversation, text: str, now: datetime
) -> Outcome:
    reply = await run_assistant(db, deps.settings, deps.provider, lead, conv, text, now)
    await send_and_record(db, deps.wa, lead, conv, reply.text, reply.buttons)
    if reply.state.booked_slot_id:
        await counselor.alert_counselors(db, deps.wa, lead, "Visit booked via chat", text)
    escalated = bool(reply.state.escalations)
    if escalated:
        conv.status = "escalated"
        reason, _urgency = reply.state.escalations[0]
        await counselor.alert_counselors(db, deps.wa, lead, reason, text)
    return Outcome("llm", reply.text, reply.buttons, escalated)


async def send_and_record(
    db: AsyncSession,
    wa: WhatsAppAdapter,
    lead: Lead,
    conv: Conversation,
    text: str,
    buttons: list[Button],
) -> str:
    to = recipient_for(lead, conv)
    if buttons:
        wamid = await wa.send_buttons(to, text, buttons)
    else:
        wamid = await wa.send_text(to, text)
    db.add(
        Message(
            conversation_id=conv.id,
            direction=Direction.OUTBOUND,
            kind="interactive" if buttons else "text",
            body=text,
            wa_message_id=wamid,
            status="sent",
            payload={"buttons": [[b.id, b.title] for b in buttons]},
        )
    )
    await db.flush()
    return wamid
