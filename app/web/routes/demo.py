"""Local pitch demo: WhatsApp-style chat with the real assistant on the seeded demo school.

Only mounted behaviour when DEMO_MODE=true. WhatsApp always goes to a fake transport.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.agents.llm import LLMError, LLMProvider
from app.agents.llm.factory import get_provider
from app.config import Settings, get_settings
from app.db import get_session
from app.models import AgentRun, Conversation, Lead, LeadEvent, Message, School
from app.models.enums import Language, LeadEventType, LeadSource
from app.schemas.lead import LeadCreate
from app.seed import SLUG
from app.services.conversation import Deps, handle_parent_message
from app.services.counselor import apply_counselor_status, counselors
from app.services.leads import create_lead, send_first_response
from app.services.templates import ALL_TEMPLATE_KEYS

TEMPLATES = Jinja2Templates(directory=Path(__file__).parents[1] / "templates")
COOKIE = "demo_lead"
QUICK_TEXT = {"book_visit": "I'd like to book a campus visit", "ask": "I have a question"}
TRANSPORT = FakeWhatsAppTransport()  # process-wide; demo only
WA = WhatsAppAdapter(TRANSPORT, set(ALL_TEMPLATE_KEYS))
Db = Annotated[AsyncSession, Depends(get_session)]


def require_demo(settings: Annotated[Settings, Depends(get_settings)]) -> Settings:
    if not settings.demo_mode:
        raise HTTPException(404)
    return settings


router = APIRouter(prefix="/demo", dependencies=[Depends(require_demo)])


def provider_or_none() -> LLMProvider | None:
    try:
        return get_provider()
    except LLMError:
        return None


async def demo_school(db: AsyncSession) -> School:
    school = await db.scalar(select(School).where(School.slug == SLUG))
    if school is None:
        raise HTTPException(503, "Demo school not seeded. Run `make seed`.")
    return school


async def current_lead(request: Request, db: AsyncSession) -> Lead | None:
    raw = request.cookies.get(COOKIE)
    return await db.get(Lead, int(raw)) if raw and raw.isdigit() else None


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Db) -> HTMLResponse:
    school = await demo_school(db)
    ctx = {
        "school": school,
        "lead": await current_lead(request, db),
        "has_key": provider_or_none() is not None,
    }
    return TEMPLATES.TemplateResponse(request, "demo/chat.html", ctx)


@router.post("/start")
async def start(
    db: Db,
    parent_name: Annotated[str, Form()],
    grade: Annotated[str, Form()],
    language: Annotated[str, Form()] = "en",
) -> Response:
    school = await demo_school(db)
    data = LeadCreate(
        source=LeadSource.WEBSITE,
        parent_name=parent_name[:60],
        phone=f"+9199999{secrets.randbelow(40000) + 50000}",  # fake range
        grade_interest=grade[:30],
        language=Language(language) if language in {"en", "hi", "hinglish"} else Language.EN,
        consent=True,
        consent_source="demo",
    )
    lead = (await create_lead(db, school.id, data)).lead
    await send_first_response(db, lead, WA)
    await db.commit()
    response = Response(
        status_code=303, headers={"Location": "/demo/chat", "HX-Redirect": "/demo/chat"}
    )
    response.set_cookie(COOKIE, str(lead.id), httponly=True, samesite="lax")
    return response


@router.post("/reset")
async def reset() -> Response:
    response = Response(
        status_code=303, headers={"Location": "/demo/chat", "HX-Redirect": "/demo/chat"}
    )
    response.delete_cookie(COOKIE)
    return response


@router.post("/send", response_class=HTMLResponse)
async def send(
    request: Request,
    db: Db,
    settings: Annotated[Settings, Depends(require_demo)],
    provider: Annotated[LLMProvider | None, Depends(provider_or_none)],
    text: Annotated[str | None, Form()] = None,
    button_id: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    lead = await current_lead(request, db)
    if lead is None:
        raise HTTPException(400, "start a conversation first")
    if provider is None:
        raise HTTPException(503, "Set OPENAI_API_KEY in .env to chat with the assistant.")
    if button_id in QUICK_TEXT:
        text, button_id = QUICK_TEXT[button_id], None
    if text or button_id:
        deps = Deps(settings, provider, WA)
        await handle_parent_message(
            db, deps, lead, text, button_id, f"demo.{uuid.uuid4().hex}", datetime.now(UTC)
        )
        await db.commit()
    return await chat_partial(request, db)


@router.get("/partials/chat", response_class=HTMLResponse)
async def chat_partial(request: Request, db: Db) -> HTMLResponse:
    lead = await current_lead(request, db)
    messages: list[Message] = []
    if lead is not None:
        conv = await db.scalar(select(Conversation).where(Conversation.lead_id == lead.id))
        if conv is not None:
            messages = list(
                (
                    await db.scalars(
                        select(Message)
                        .where(Message.conversation_id == conv.id)
                        .order_by(Message.id)
                    )
                ).all()
            )
    ctx = {"lead": lead, "messages": messages}
    return TEMPLATES.TemplateResponse(request, "demo/_chat.html", ctx)


@router.get("/partials/side", response_class=HTMLResponse)
async def side_partial(request: Request, db: Db) -> HTMLResponse:
    school = await demo_school(db)
    lead = await current_lead(request, db)
    alerts: list[dict[str, Any]] = []
    events: list[LeadEvent] = []
    if lead is not None:
        marker = f"lead:{lead.id}:"
        alerts = [
            p
            for p in TRANSPORT.sent
            if p.get("type") == "template"
            and any(marker in str(c) for c in p["template"]["components"])
        ]
        events = list(
            (
                await db.scalars(
                    select(LeadEvent)
                    .where(LeadEvent.lead_id == lead.id)
                    .order_by(LeadEvent.id.desc())
                )
            ).all()
        )
    runs = (
        await db.scalars(
            select(AgentRun)
            .where(AgentRun.school_id == school.id)
            .order_by(AgentRun.id.desc())
            .limit(15)
        )
    ).all()
    ctx = {"lead": lead, "alerts": alerts[-3:][::-1], "events": events, "runs": runs}
    return TEMPLATES.TemplateResponse(request, "demo/_side.html", ctx)


@router.post("/counselor/{event}", response_class=HTMLResponse)
async def counselor_tap(request: Request, db: Db, event: LeadEventType) -> HTMLResponse:
    lead = await current_lead(request, db)
    if lead is None:
        raise HTTPException(400)
    staff = await counselors(db, lead.school_id)
    if staff and staff[0].whatsapp_number:
        await apply_counselor_status(
            db, staff[0].whatsapp_number, lead.id, event, f"demo.{uuid.uuid4().hex}"
        )
        await db.commit()
    return await side_partial(request, db)
