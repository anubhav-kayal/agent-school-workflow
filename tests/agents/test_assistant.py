from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assistant import run_assistant
from app.agents.llm import LLMError, LLMRequest, LLMTurn
from app.agents.llm.fake import ScriptedProvider, text_turn, tool_turn
from app.config import Settings
from app.models import AgentRun, Conversation, Lead, Message, School
from app.models.enums import Direction, LeadSource
from app.seed import SLUG, seed

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)
SETTINGS = Settings(_env_file=None)  # type: ignore[call-arg]


async def parent_says(db: AsyncSession, text: str) -> tuple[Lead, Conversation]:
    await seed(db, today=date(2026, 11, 2))
    school = await db.scalar(select(School).where(School.slug == SLUG))
    assert school is not None
    lead = Lead(
        school_id=school.id,
        source=LeadSource.WEBSITE,
        phone="+919999900010",
        parent_name="Test Parent",
    )
    db.add(lead)
    await db.flush()
    conv = Conversation(lead_id=lead.id, school_id=school.id, last_inbound_at=NOW)
    db.add(conv)
    await db.flush()
    db.add(Message(conversation_id=conv.id, direction=Direction.INBOUND, kind="text", body=text))
    await db.flush()
    return lead, conv


async def test_unverified_fact_triggers_escalation_not_answer(db: AsyncSession) -> None:
    lead, conv = await parent_says(db, "What were the class 10 board results last year?")
    provider = ScriptedProvider(
        [
            tool_turn("get_school_facts", topic="results"),
            tool_turn(
                "escalate_to_counselor", call_id="c2", reason="results not in KB", urgency="normal"
            ),
            text_turn("A counselor will confirm the results and get back to you."),
        ]
    )
    reply = await run_assistant(db, SETTINGS, provider, lead, conv, "class 10 results?", NOW)
    assert reply.state.escalations == [("results not in KB", "normal")]
    assert "98%" not in reply.text
    first: LLMRequest = provider.requests[0]
    context = first.items[0]["content"]
    assert "fees.class_1" in context and "98%" not in context  # unverified never sent
    assert first.items[-1]["content"] == "LANGUAGE_HINT: en"
    assert "store" not in first.__dict__  # provider decides; agents never see SDK options


async def test_slots_become_buttons(db: AsyncSession) -> None:
    lead, conv = await parent_says(db, "Can I visit the campus this week?")
    provider = ScriptedProvider(
        [
            tool_turn("get_visit_slots", from_date=None, to_date=None),
            text_turn("Sure! Please pick a time below."),
        ]
    )
    reply = await run_assistant(db, SETTINGS, provider, lead, conv, "visit?", NOW)
    assert 1 <= len(reply.buttons) <= 3
    assert all(b.id.startswith("slot:") for b in reply.buttons)
    run = await db.get_one(AgentRun, reply.agent_run_id)
    assert run.model == "gpt-6-luna" and run.output["tools"] == ["get_visit_slots"]


class FailingProvider(ScriptedProvider):
    async def respond(self, request: LLMRequest) -> LLMTurn:
        raise LLMError("api error 500")


async def test_llm_failure_falls_back_in_parents_language(db: AsyncSession) -> None:
    lead, conv = await parent_says(db, "फीस कितनी है?")
    reply = await run_assistant(db, SETTINGS, FailingProvider([]), lead, conv, "फीस कितनी है?", NOW)
    assert reply.language == "hi"
    assert "काउंसलर" in reply.text
    assert reply.state.escalations == [("assistant error", "normal")]
    run = await db.get_one(AgentRun, reply.agent_run_id)
    assert run.status == "error"
