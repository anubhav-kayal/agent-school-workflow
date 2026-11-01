from datetime import UTC, date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fakes.meta_leads import FakeMetaLeadClient
from app.adapters.meta_leads import MetaLead
from app.agents.llm.fake import ScriptedProvider, text_turn
from app.config import Settings
from app.jobs import worker
from app.models import Lead
from app.seed import seed
from tests.adapters.test_meta_leads import GRAPH_LEAD


class OneSession:
    """Hands the test's rolled-back session to job code that opens its own session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def __call__(self) -> "OneSession":
        return self

    async def __aenter__(self) -> AsyncSession:
        return self.db

    async def __aexit__(self, *exc: object) -> None:
        return None


async def ctx_for(db: AsyncSession, *turns: object) -> dict[str, Any]:
    await seed(db, today=date(2026, 11, 2))
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    http = httpx.AsyncClient()
    return {
        "settings": settings,
        "http": http,
        "sessions": OneSession(db),
        "wa": worker.build_whatsapp(settings, http),
        "provider": ScriptedProvider(list(turns)),  # type: ignore[arg-type]
        "meta": FakeMetaLeadClient({"444444444": MetaLead.from_graph(GRAPH_LEAD)}),
    }


def test_dry_run_uses_logging_transport_even_with_token() -> None:
    settings = Settings(_env_file=None, whatsapp_token="FAKE", whatsapp_phone_number_id="1")  # type: ignore[call-arg]
    wa = worker.build_whatsapp(settings, httpx.AsyncClient())
    assert isinstance(wa.transport, worker.DryRunTransport)


def test_reminders_scheduled_every_15_minutes() -> None:
    [job] = worker.WorkerSettings.cron_jobs
    assert job.minute == {0, 15, 30, 45}


async def test_meta_lead_job_sends_template_with_no_llm(db: AsyncSession) -> None:
    ctx = await ctx_for(db)  # provider has no turns: any LLM call would raise
    started = datetime.now(UTC)
    assert await worker.process_meta_lead(ctx, "444444444", "000000000000001") is True
    lead = await db.scalar(select(Lead).where(Lead.external_lead_id == "444444444"))
    assert lead is not None and lead.first_response_at is not None
    assert (lead.first_response_at - started).total_seconds() < 60
    [sent] = ctx["wa"].transport.sent
    assert sent["type"] == "template"
    assert ctx["provider"].requests == []


async def test_whatsapp_job_runs_assistant(db: AsyncSession) -> None:
    ctx = await ctx_for(db, text_turn("Hello! How can I help?"))
    route = await worker.process_whatsapp_message(
        ctx,
        phone_number_id="000000000000002",
        sender="+919999900070",
        wa_message_id="wamid.JOB1",
        sent_at=datetime.now(UTC).isoformat(),
        text="Hi",
        button_id=None,
    )
    assert route == "llm"
    assert ctx["wa"].transport.sent[0]["text"]["body"] == "Hello! How can I help?"
