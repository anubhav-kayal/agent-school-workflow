"""arq worker: lead intake, inbound WhatsApp, first response and reminders.

Run with `make worker`. In DRY_RUN (default) WhatsApp goes to a logging transport.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.meta_leads import GraphLeadClient
from app.adapters.whatsapp import WhatsAppAdapter
from app.adapters.whatsapp_cloud import CloudApiTransport
from app.adapters.whatsapp_inbound import InboundMessage
from app.agents.llm import LLMError, LLMRequest, LLMTurn
from app.agents.llm.factory import get_provider
from app.agents.llm.fake import ScriptedProvider
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.models import Lead
from app.services.conversation import Deps
from app.services.inbound_whatsapp import process_whatsapp_message as process_message
from app.services.intake import ingest_meta_lead
from app.services.leads import send_first_response as send_first
from app.services.reminders import send_due_reminders
from app.services.templates import ALL_TEMPLATE_KEYS

log = logging.getLogger(__name__)


class DryRunTransport(FakeWhatsAppTransport):
    async def send(self, payload: dict[str, Any]) -> str:
        log.info("DRY_RUN whatsapp → %s %s", payload["to"][-4:], payload["type"])
        return await super().send(payload)


class UnavailableProvider(ScriptedProvider):
    """No API key: every assistant turn falls back to the polite escalation reply."""

    async def respond(self, request: LLMRequest) -> LLMTurn:
        raise LLMError("OPENAI_API_KEY is not set")


def build_whatsapp(settings: Settings, http: httpx.AsyncClient) -> WhatsAppAdapter:
    token = settings.whatsapp_token.get_secret_value() if settings.whatsapp_token else ""
    if settings.dry_run or not token or not settings.whatsapp_phone_number_id:
        return WhatsAppAdapter(DryRunTransport(), set(ALL_TEMPLATE_KEYS))
    approved = {tuple(t.split(":", 1)) for t in settings.whatsapp_approved_templates}
    transport = CloudApiTransport(
        http, token, settings.whatsapp_phone_number_id, settings.meta_graph_version
    )
    return WhatsAppAdapter(transport, approved)  # type: ignore[arg-type]


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    http = httpx.AsyncClient()
    token = settings.meta_system_user_token
    try:
        provider = get_provider()
    except LLMError:
        provider = UnavailableProvider([])
    ctx.update(
        settings=settings,
        http=http,
        sessions=get_sessionmaker(),
        wa=build_whatsapp(settings, http),
        provider=provider,
        meta=GraphLeadClient(http, token.get_secret_value(), settings.meta_graph_version)
        if token
        else None,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["http"].aclose()


def _sessions(ctx: dict[str, Any]) -> Callable[[], AsyncSession]:
    sessions: Callable[[], AsyncSession] = ctx["sessions"]
    return sessions


async def send_first_response(ctx: dict[str, Any], lead_id: int) -> bool:
    async with _sessions(ctx)() as db:
        lead = await db.get(Lead, lead_id)
        sent = lead is not None and await send_first(db, lead, ctx["wa"])
        await db.commit()
        return sent


async def process_meta_lead(ctx: dict[str, Any], leadgen_id: str, page_id: str) -> bool:
    if ctx["meta"] is None:
        raise RuntimeError("META_SYSTEM_USER_TOKEN not set; cannot fetch leads")
    async with _sessions(ctx)() as db:
        lead = await ingest_meta_lead(db, ctx["meta"], page_id, leadgen_id)
        sent = lead is not None and await send_first(db, lead, ctx["wa"])  # same job: SLA
        await db.commit()
        return sent


async def process_whatsapp_message(ctx: dict[str, Any], **fields: Any) -> str:
    msg = InboundMessage(**{**fields, "sent_at": datetime.fromisoformat(fields["sent_at"])})
    async with _sessions(ctx)() as db:
        deps = Deps(ctx["settings"], ctx["provider"], ctx["wa"])
        route = await process_message(db, deps, msg)
        await db.commit()
        return route


async def send_reminders(ctx: dict[str, Any]) -> int:
    async with _sessions(ctx)() as db:
        sent = await send_due_reminders(db, ctx["wa"], datetime.now(UTC))
        await db.commit()
        return sent


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        send_first_response,
        process_meta_lead,
        process_whatsapp_message,
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(send_reminders, minute={0, 15, 30, 45}, run_at_startup=False)
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 120
