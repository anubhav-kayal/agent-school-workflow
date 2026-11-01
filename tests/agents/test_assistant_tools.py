import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assistant_tools import SPECS, TurnState, build_tools
from app.models import KbFact, Lead, School, VisitSlot
from app.models.enums import Language, LeadSource, LeadStatus

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)


def test_tool_schemas_are_strict() -> None:
    for spec in SPECS.values():
        params = spec.parameters
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


async def tools_for(db: AsyncSession) -> tuple[dict, TurnState, Lead]:  # type: ignore[type-arg]
    school = School(name="Demo", slug="demo-tools", city="Pune")
    db.add(school)
    await db.flush()
    lead = Lead(school_id=school.id, source=LeadSource.WEBSITE, phone="+919999900007")
    db.add_all(
        [
            lead,
            KbFact(
                school_id=school.id,
                topic="fees",
                key="fees.class_1",
                value="₹85,000",
                verified=True,
            ),
            KbFact(
                school_id=school.id,
                topic="results",
                key="results.class_10_2026",
                value="98%",
                verified=False,
            ),
            *[
                VisitSlot(school_id=school.id, starts_at=NOW + timedelta(days=d), capacity=2)
                for d in (1, 2, 3, 4)
            ],
        ]
    )
    await db.flush()
    state = TurnState()
    tools = {t.spec.name: t.handler for t in build_tools(db, lead, NOW, state)}
    return tools, state, lead


async def test_unverified_fact_is_never_returned(db: AsyncSession) -> None:
    tools, _, _ = await tools_for(db)
    out = json.loads(await tools["get_school_facts"]({"topic": "results"}))
    assert out["facts"] == [] and "escalate" in out["instruction"]
    fees = json.loads(await tools["get_school_facts"]({"topic": "fees"}))
    assert fees["facts"][0]["value"] == "₹85,000"


async def test_slots_offered_max_three_then_booked(db: AsyncSession) -> None:
    tools, state, lead = await tools_for(db)
    out = json.loads(await tools["get_visit_slots"]({"from_date": None, "to_date": None}))
    assert len(out["slots"]) == 3 == len(state.offered_slots)
    slot_id = out["slots"][0]["slot_id"]
    assert json.loads(await tools["book_visit"]({"slot_id": slot_id}))["ok"] is True
    assert state.booked_slot_id == slot_id
    assert lead.status is LeadStatus.VISIT_BOOKED


async def test_escalate_and_language_and_not_interested(db: AsyncSession) -> None:
    tools, state, lead = await tools_for(db)
    await tools["escalate_to_counselor"]({"reason": "results not in KB", "urgency": "normal"})
    await tools["set_language"]({"language": "hi"})
    await tools["mark_not_interested"]({"reason": "moved city"})
    assert state.escalations == [("results not in KB", "normal")]
    assert lead.language is Language.HI
    assert lead.status is LeadStatus.NOT_INTERESTED
