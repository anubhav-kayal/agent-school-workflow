"""Admission assistant: one parent message in, one WhatsApp-ready reply out."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.whatsapp import Button
from app.agents.assistant_tools import TurnState, build_tools
from app.agents.base import log_run, run_tool_loop
from app.agents.language import detect_language
from app.agents.llm import LLMError, LLMProvider, LLMRequest, Usage
from app.agents.llm.types import Item
from app.config import AgentName, Settings
from app.models import Conversation, Lead, Message, School
from app.models.enums import Direction
from app.services import kb

PROMPT = (Path(__file__).parent / "prompts" / "assistant.md").read_text(encoding="utf-8")
HISTORY_LIMIT = 12
FALLBACK = {
    "en": "Thank you for your message. A counselor from the school will get back to you shortly.",
    "hi": "आपके मैसेज के लिए धन्यवाद। स्कूल के काउंसलर जल्द ही आपसे संपर्क करेंगे।",
    "hinglish": "Aapke message ke liye dhanyavaad. School ke counselor jaldi aapse baat karenge.",
}


@dataclass
class AssistantReply:
    text: str
    language: str
    buttons: list[Button] = field(default_factory=list)
    state: TurnState = field(default_factory=TurnState)
    agent_run_id: int | None = None
    usage: Usage = field(default_factory=Usage)


async def school_context(db: AsyncSession, school: School) -> str:
    """Per-school block placed right after the static prompt (stable → cached)."""
    facts = await kb.verified_facts(db, school.id)
    topics = await kb.topics(db, school.id)
    return (
        f"SCHOOL: {school.name}, {school.city}\nTOPICS: {', '.join(topics)}\n"
        f"VERIFIED_FACTS: {kb.kb_prompt_block(facts)}"
    )


async def history_items(db: AsyncSession, provider: LLMProvider, conv: Conversation) -> list[Item]:
    rows = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.desc())
            .limit(HISTORY_LIMIT)
        )
    ).all()
    items = []
    for m in reversed(rows):
        text = m.body or f"[template sent: {m.template_name}]"
        items.append(
            provider.user_item(text)
            if m.direction == Direction.INBOUND
            else provider.assistant_item(text)
        )
    return items


async def run_assistant(
    db: AsyncSession,
    settings: Settings,
    provider: LLMProvider,
    lead: Lead,
    conv: Conversation,
    latest_text: str,
    now: datetime,
) -> AssistantReply:
    started = time.monotonic()
    cfg = settings.agent(AgentName.ASSISTANT)
    school = await db.get_one(School, lead.school_id)
    language = detect_language(latest_text)
    items = [
        provider.context_item(await school_context(db, school)),
        *await history_items(db, provider, conv),
        provider.context_item(f"LANGUAGE_HINT: {language}"),
    ]
    request = LLMRequest(
        model=settings.model_for(AgentName.ASSISTANT),
        instructions=PROMPT,
        items=items,
        reasoning_effort=cfg.reasoning_effort,
        max_output_tokens=cfg.max_output_tokens,
        cache_key=f"school:{school.id}:assistant",
    )
    state = TurnState()
    summary = {"lead_id": lead.id, "language_hint": language, "history": len(items) - 2}
    try:
        result = await run_tool_loop(
            provider,
            request,
            build_tools(db, lead, now, state),
            cfg.max_tool_iterations,
            cfg.token_budget,
        )
    except LLMError as exc:
        state.escalations.append(("assistant error", "normal"))
        run = await log_run(
            db,
            settings,
            AgentName.ASSISTANT,
            school.id,
            Usage(),
            started,
            summary,
            {},
            status="error",
            error=str(exc),
        )
        return AssistantReply(FALLBACK[language], language, state=state, agent_run_id=run.id)
    buttons = (
        []
        if state.booked_slot_id
        else [Button(f"slot:{slot_id}", label) for slot_id, label in state.offered_slots]
    )
    text = result.text.strip() or FALLBACK[language]
    run = await log_run(
        db,
        settings,
        AgentName.ASSISTANT,
        school.id,
        result.usage,
        started,
        summary,
        {"reply": text, "tools": [c.name for c in result.calls], "escalations": state.escalations},
    )
    return AssistantReply(text, language, buttons, state, run.id, result.usage)
