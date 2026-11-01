"""Run assistant eval scenarios against the REAL model (costs money; never in CI).

    uv run python -m evals.runner --tier tier_fast [--only id1,id2]

Each scenario runs inside a DB transaction on the dev database that is rolled back.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import WhatsAppAdapter
from app.agents.llm.factory import get_provider
from app.config import AgentName, LlmTier, Settings, get_settings
from app.models import AgentRun, Conversation, Lead, Message, School, VisitSlot
from app.models.enums import Actor, Direction, Language, LeadSource, LeadStatus
from app.seed import SLUG, seed
from app.services.conversation import Deps, handle_parent_message
from app.services.templates import ALL_TEMPLATE_KEYS
from app.services.visits import book_visit
from evals.scoring import Transcript, score

ROOT = Path(__file__).parent
PHONE = "+919999909999"


def load_scenarios(only: set[str] | None) -> list[dict[str, Any]]:
    out = []
    for path in sorted((ROOT / "scenarios").glob("*.yaml")):
        out += [
            s for s in yaml.safe_load(path.read_text())["scenarios"] if not only or s["id"] in only
        ]
    return out


async def setup_lead(db: AsyncSession, scenario: dict[str, Any], now: datetime) -> Lead:
    await seed(db)
    school = await db.scalar(select(School).where(School.slug == SLUG))
    assert school is not None
    setup = scenario.get("setup", {})
    lead = Lead(
        school_id=school.id,
        source=LeadSource.META_LEAD_AD,
        phone=PHONE,
        parent_name="Test Parent",
        grade_interest=setup.get("grade", "Class 1"),
        language=Language(setup.get("language", "en")),
        consent=True,
        status=LeadStatus.CONTACTED,
        first_response_at=now,
    )
    db.add(lead)
    await db.flush()
    conv = Conversation(lead_id=lead.id, school_id=school.id, last_inbound_at=now)
    db.add(conv)
    await db.flush()
    for prior in setup.get("history", []):
        direction = Direction.INBOUND if prior["from"] == "parent" else Direction.OUTBOUND
        db.add(
            Message(conversation_id=conv.id, direction=direction, kind="text", body=prior["text"])
        )
    if setup.get("booked"):
        slot = await db.scalar(
            select(VisitSlot).where(VisitSlot.starts_at > now).order_by(VisitSlot.starts_at)
        )
        assert slot is not None
        await book_visit(db, lead, slot.id, Actor.ASSISTANT)
    await db.flush()
    return lead


async def run_scenario(db: AsyncSession, deps: Deps, scenario: dict[str, Any]) -> Transcript:
    now = datetime.now(UTC)
    lead = await setup_lead(db, scenario, now)
    transport: FakeWhatsAppTransport = deps.wa.transport  # type: ignore[assignment]
    transport.sent.clear()
    t = Transcript()
    first_run_id = (await db.scalar(select(AgentRun.id).order_by(AgentRun.id.desc()))) or 0
    last_buttons: list[str] = []
    for i, turn in enumerate(scenario["turns"]):
        text, button = (turn, None) if isinstance(turn, str) else (None, turn.get("button"))
        if button == "first_offered_slot":
            button = last_buttons[0] if last_buttons else None
        out = await handle_parent_message(db, deps, lead, text, button, f"eval.{i}", now)
        t.routes.append(out.route)
        t.escalated |= out.escalated
        for payload in transport.to(PHONE)[len(t.replies) :]:
            body = payload.get("text", {}).get("body") or payload["interactive"]["body"]["text"]
            t.replies.append(body)
            buttons = payload.get("interactive", {}).get("action", {}).get("buttons", [])
            last_buttons = [b["reply"]["id"] for b in buttons] or last_buttons
            t.buttons_offered += len(buttons)
    runs = (await db.scalars(select(AgentRun).where(AgentRun.id > first_run_id))).all()
    t.tools = [tool for r in runs for tool in r.output.get("tools", [])]
    t.cost_usd = sum(float(r.cost_usd) for r in runs)
    t.cost_inr = sum(float(r.cost_inr) for r in runs)
    t.llm_calls = len(runs)
    t.booked = lead.status == LeadStatus.VISIT_BOOKED and bool(scenario.get("turns"))
    return t


async def main(tier: str, only: set[str] | None) -> None:
    settings = get_settings()
    settings.agents[AgentName.ASSISTANT] = settings.agent(AgentName.ASSISTANT).model_copy(
        update={"tier": LlmTier(tier)}
    )
    deps = Deps(
        settings, get_provider(), WhatsAppAdapter(FakeWhatsAppTransport(), set(ALL_TEMPLATE_KEYS))
    )
    engine = create_async_engine(settings.database_url)
    results = []
    for scenario in load_scenarios(only):
        async with engine.connect() as conn:
            trans = await conn.begin()
            db = AsyncSession(
                bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            try:
                transcript = await run_scenario(db, deps, scenario)
            finally:
                await db.close()
                await trans.rollback()
        checks = score(scenario["expect"], transcript)
        passed = all(c.passed for c in checks)
        results.append(
            {
                "id": scenario["id"],
                "passed": passed,
                "transcript": asdict(transcript),
                "checks": [asdict(c) for c in checks],
            }
        )
        print(
            f"{'PASS' if passed else 'FAIL'}  {scenario['id']}"
            + "".join(f"\n      ✗ {c.name}: {c.detail}" for c in checks if not c.passed)
        )
    await engine.dispose()
    report(results, settings, tier)


def report(results: list[dict[str, Any]], settings: Settings, tier: str) -> None:
    n = len(results)
    passed = sum(r["passed"] for r in results)
    usd = sum(r["transcript"]["cost_usd"] for r in results)
    inr = sum(r["transcript"]["cost_inr"] for r in results)
    summary = {
        "tier": tier,
        "model": settings.tiers[LlmTier(tier)],
        "scenarios": n,
        "passed": passed,
        "pass_rate": round(passed / n, 3) if n else 0,
        "avg_cost_usd_per_conversation": round(usd / n, 6) if n else 0,
        "avg_cost_inr_per_conversation": round(inr / n, 4) if n else 0,
        "run_at": datetime.now(UTC).isoformat(),
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "results" / f"assistant_{tier}_{stamp}.json"
    out.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False)
    )
    print(json.dumps(summary, indent=2), f"\nSaved {out}")


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default="tier_fast", choices=[t.value for t in LlmTier])
    parser.add_argument("--only", help="comma-separated scenario ids")
    args = parser.parse_args()
    asyncio.run(main(args.tier, set(args.only.split(",")) if args.only else None))


if __name__ == "__main__":
    cli()
