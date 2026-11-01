import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Creative, KbFact, ProposedAction, School
from app.models.enums import ActionStatus, ActionType, CreativeStatus, Language


async def make_school(db: AsyncSession) -> School:
    school = School(name="Demo", slug="demo-kb", city="Pune")
    db.add(school)
    await db.flush()
    return school


async def test_kb_fact_unverified_by_default_and_unique_key(db: AsyncSession) -> None:
    school = await make_school(db)
    fact = KbFact(school_id=school.id, topic="fees", key="fees.class_1", value="₹85,000 / year")
    db.add(fact)
    await db.flush()
    await db.refresh(fact)
    assert fact.verified is False
    db.add(KbFact(school_id=school.id, topic="fees", key="fees.class_1", value="dup"))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_proposal_defaults_pending_and_links_run(db: AsyncSession) -> None:
    school = await make_school(db)
    run = AgentRun(agent="optimizer", school_id=school.id, model="claude-sonnet-5-5")
    db.add(run)
    await db.flush()
    action = ProposedAction(
        agent_run_id=run.id, school_id=school.id, type=ActionType.NO_ACTION, reason="Learning phase"
    )
    db.add(action)
    await db.flush()
    assert action.status is ActionStatus.PENDING


async def test_creative_starts_as_draft(db: AsyncSession) -> None:
    school = await make_school(db)
    c = Creative(
        school_id=school.id,
        grade="nursery",
        angle="safety",
        language=Language.HI,
        primary_text="…",
        headline="Admissions open",
        cta="LEARN_MORE",
        claims_used=[1],
    )
    db.add(c)
    await db.flush()
    assert c.status is CreativeStatus.DRAFT
    assert c.claims_used == [1]
