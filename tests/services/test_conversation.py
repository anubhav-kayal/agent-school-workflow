from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.agents.llm.fake import ScriptedProvider, text_turn, tool_turn
from app.config import Settings
from app.models import Lead, School, VisitSlot
from app.models.enums import LeadSource, LeadStatus
from app.seed import SLUG, seed
from app.services.conversation import Deps, handle_parent_message
from app.services.leads import send_first_response

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)
PARENT = "919999900020"
COUNSELOR = "919999900102"
TEMPLATES = {("enquiry_first_response", "en"), ("counselor_lead_alert", "en")}


async def setup(db: AsyncSession, *turns: object) -> tuple[Lead, Deps, FakeWhatsAppTransport]:
    await seed(db, today=date(2026, 11, 2))
    school = await db.scalar(select(School).where(School.slug == SLUG))
    assert school
    lead = Lead(
        school_id=school.id,
        source=LeadSource.WEBSITE,
        phone="+" + PARENT,
        parent_name="Test Parent",
    )
    db.add(lead)
    await db.flush()
    transport = FakeWhatsAppTransport()
    deps = Deps(
        Settings(_env_file=None),  # type: ignore[call-arg]
        ScriptedProvider(list(turns)),
        WhatsAppAdapter(transport, TEMPLATES),
    )  # type: ignore[arg-type]
    return lead, deps, transport


async def test_stop_silences_everything_afterwards(db: AsyncSession) -> None:
    lead, deps, transport = await setup(db)
    out = await handle_parent_message(db, deps, lead, "STOP", None, "wamid.IN1", NOW)
    assert out.route == "opt_out" and lead.opted_out_at == NOW
    out = await handle_parent_message(db, deps, lead, "Hello? fees?", None, "wamid.IN2", NOW)
    assert out.route == "opted_out"
    assert await send_first_response(db, lead, deps.wa) is False
    assert transport.to(PARENT) == []  # nothing ever sent to the parent


async def test_slot_button_books_without_llm_and_alerts_counselor(db: AsyncSession) -> None:
    lead, deps, transport = await setup(db)  # provider has no turns: an LLM call would fail
    slot = await db.scalar(select(VisitSlot).order_by(VisitSlot.starts_at))
    assert slot
    out = await handle_parent_message(db, deps, lead, "Tue", f"slot:{slot.id}", "wamid.B1", NOW)
    assert out.route == "book_slot" and lead.status is LeadStatus.VISIT_BOOKED
    assert "booked" in transport.to(PARENT)[0]["text"]["body"]
    assert transport.to(COUNSELOR)[0]["template"]["name"] == "counselor_lead_alert"


async def test_escalation_alerts_counselor(db: AsyncSession) -> None:
    lead, deps, transport = await setup(
        db,
        tool_turn("escalate_to_counselor", reason="wants discount", urgency="normal"),
        text_turn("A counselor will call you about this."),
    )
    out = await handle_parent_message(db, deps, lead, "Any discount?", None, "wamid.D1", NOW)
    assert out.escalated
    assert transport.bodies(PARENT)[0].startswith("A counselor")
    assert len(transport.to(COUNSELOR)) == 1


async def test_duplicate_webhook_delivery_ignored(db: AsyncSession) -> None:
    lead, deps, transport = await setup(db, text_turn("Hello!"))
    await handle_parent_message(db, deps, lead, "Hi", None, "wamid.DUP", NOW)
    out = await handle_parent_message(db, deps, lead, "Hi", None, "wamid.DUP", NOW)
    assert out.route == "duplicate"
    assert len(transport.to(PARENT)) == 1


async def test_language_asked_once_then_preference_applied(db: AsyncSession) -> None:
    lead, deps, transport = await setup(
        db, text_turn("Class 1 fees are ₹85,000."), text_turn("Transport covers Baner.")
    )
    await handle_parent_message(db, deps, lead, "fees?", None, "wamid.L1", NOW)
    first = transport.to(PARENT)[-1]
    ids = [b["reply"]["id"] for b in first["interactive"]["action"]["buttons"]]
    assert ids == ["lang:en", "lang:hi", "lang:hinglish"] and lead.language_asked_at == NOW

    out = await handle_parent_message(db, deps, lead, "Hinglish", "lang:hinglish", "wamid.L2", NOW)
    assert out.route == "set_language" and lead.language.value == "hinglish"
    assert lead.language_confirmed_at == NOW
    assert transport.to(PARENT)[-1]["text"]["body"].startswith("Theek hai, ab se hum Hinglish")

    await handle_parent_message(db, deps, lead, "bus?", None, "wamid.L3", NOW)
    assert transport.to(PARENT)[-1]["type"] == "text"  # not asked again
