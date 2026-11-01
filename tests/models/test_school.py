import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdAccount, GuardrailConfig, School, User
from app.models.enums import AutonomyLevel, Platform, UserRole


def demo_school(slug: str = "demo") -> School:
    return School(name="Demo Public School", slug=slug, city="Pune")


async def test_school_safety_defaults(db: AsyncSession) -> None:
    school = demo_school()
    db.add(school)
    await db.flush()
    await db.refresh(school)
    assert school.dry_run is True
    assert school.kill_switch is False
    assert school.autonomy_level is AutonomyLevel.L0
    assert school.timezone == "Asia/Kolkata"
    assert school.languages == ["en"]


async def test_raw_insert_still_gets_safe_defaults(db: AsyncSession) -> None:
    await db.execute(
        text(
            "INSERT INTO schools (name, slug, city, timezone, languages, brand) "
            "VALUES ('Raw', 'raw', 'Delhi', 'Asia/Kolkata', '{en}', '{}')"
        )
    )
    row = (
        await db.execute(
            text("SELECT dry_run, kill_switch, autonomy_level FROM schools WHERE slug = 'raw'")
        )
    ).one()
    assert tuple(row) == (True, False, "L0")


async def test_guardrail_defaults(db: AsyncSession) -> None:
    school = demo_school()
    school.guardrails = GuardrailConfig()
    db.add(school)
    await db.flush()
    g = (await db.execute(select(GuardrailConfig))).scalar_one()
    assert g.max_daily_budget_change_pct == 20
    assert g.max_budget_edits_per_ad_set_per_day == 1
    assert g.min_hours_between_edits == 24


async def test_invalid_autonomy_level_rejected(db: AsyncSession) -> None:
    db.add(demo_school())
    await db.flush()
    with pytest.raises(IntegrityError):
        await db.execute(text("UPDATE schools SET autonomy_level = 'L9'"))


async def test_ad_account_unique_per_platform(db: AsyncSession) -> None:
    school = demo_school()
    db.add(school)
    await db.flush()
    for _ in range(2):
        db.add(
            AdAccount(
                school_id=school.id,
                platform=Platform.META,
                external_id="act_000",
                credentials_ref="META_SYSTEM_USER_TOKEN",
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_user_email_unique(db: AsyncSession) -> None:
    for _ in range(2):
        db.add(User(email="admin@example.test", role=UserRole.ADMIN))
    with pytest.raises(IntegrityError):
        await db.flush()
