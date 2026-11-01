"""Idempotent demo seed. ALL DATA IS FAKE: example.test emails, +9199999xxxxx numbers.

Run with `make seed`. Safe to run repeatedly.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.models import AdAccount, GuardrailConfig, KbFact, School, User, VisitSlot
from app.models.enums import Platform, UserRole

IST = ZoneInfo("Asia/Kolkata")
SLUG = "demo-sunrise"

USERS: list[dict[str, Any]] = [
    {"email": "admin@example.test", "role": UserRole.ADMIN, "school": False},
    {"email": "strategist@example.test", "role": UserRole.STRATEGIST, "school": False},
    {
        "email": "principal@example.test",
        "role": UserRole.SCHOOL_APPROVER,
        "school": True,
        "whatsapp_number": "+919999900101",
    },
    {"email": "viewer@example.test", "role": UserRole.SCHOOL_VIEWER, "school": True},
    {
        "email": "counselor@example.test",
        "role": UserRole.COUNSELOR,
        "school": True,
        "whatsapp_number": "+919999900102",
    },
]

# (topic, key, value, verified). One deliberately unverified fact to exercise escalation.
KB_FACTS: list[tuple[str, str, str, bool]] = [
    ("board", "board.affiliation", "CBSE (affiliation no. DEMO-0000)", True),
    ("fees", "fees.nursery", "₹65,000 per year (tuition), payable in 4 instalments", True),
    ("fees", "fees.class_1", "₹85,000 per year (tuition), payable in 4 instalments", True),
    ("fees", "fees.admission", "One-time admission fee ₹15,000", True),
    ("transport", "transport.areas", "Kothrud, Baner, Aundh, Pashan", True),
    ("transport", "transport.fee", "₹2,500 per month", True),
    ("admissions", "admissions.grades_open", "Nursery to Class 9 for 2027-28", True),
    ("admissions", "admissions.documents", "Birth certificate, 2 photos, address proof", True),
    ("campus", "campus.address", "Plot 0, Demo Road, Pune 411000", True),
    ("campus", "campus.visit_hours", "Mon–Sat, 10:00–13:00 and 15:00–17:00", True),
    ("results", "results.class_10_2026", "98% pass rate (unconfirmed)", False),
]


async def upsert_school(db: AsyncSession) -> int:
    stmt = (
        insert(School)
        .values(
            name="Sunrise Demo Public School",
            slug=SLUG,
            city="Pune",
            timezone="Asia/Kolkata",
            languages=["en", "hi", "hinglish"],
            monthly_budget_cap_paise=30_00_000_00,
            daily_budget_cap_paise=1_00_000_00,
            monthly_llm_budget_usd=50,
            brand={"primary": "#0B5FA5", "secondary": "#F2A900", "logo": "brand/demo-logo.png"},
        )
        .on_conflict_do_update(index_elements=["slug"], set_={"name": "Sunrise Demo Public School"})
    )
    school_id = (await db.execute(stmt.returning(School.id))).scalar_one()
    await db.execute(insert(GuardrailConfig).values(school_id=school_id).on_conflict_do_nothing())
    return school_id


async def upsert_users(db: AsyncSession, school_id: int) -> None:
    for u in USERS:
        values = {
            "email": u["email"],
            "role": u["role"],
            "school_id": school_id if u["school"] else None,
            "whatsapp_number": u.get("whatsapp_number"),
        }
        await db.execute(
            insert(User).values(**values).on_conflict_do_nothing(index_elements=["email"])
        )


async def upsert_ad_accounts(db: AsyncSession, school_id: int) -> None:
    rows = [
        (Platform.META, "act_000000000001", "META_SYSTEM_USER_TOKEN"),
        (Platform.GOOGLE, "0000000001", "GOOGLE_ADS_REFRESH_TOKEN"),
    ]
    for platform, external_id, ref in rows:
        await db.execute(
            insert(AdAccount)
            .values(
                school_id=school_id,
                platform=platform,
                external_id=external_id,
                name=f"Demo {platform.value}",
                credentials_ref=ref,
            )
            .on_conflict_do_nothing(index_elements=["platform", "external_id"])
        )


async def upsert_kb(db: AsyncSession, school_id: int) -> None:
    now = datetime.now(UTC)
    for topic, key, value, verified in KB_FACTS:
        stmt = insert(KbFact).values(
            school_id=school_id,
            topic=topic,
            key=key,
            value=value,
            verified=verified,
            verified_at=now if verified else None,
        )
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["school_id", "key"],
                set_={"value": stmt.excluded.value, "verified": stmt.excluded.verified},
            )
        )


def slot_times(start: date, days: int = 14) -> list[datetime]:
    """10:00 and 15:00 IST, Monday–Saturday, as UTC datetimes."""
    out = []
    for offset in range(1, days + 1):
        d = start + timedelta(days=offset)
        if d.weekday() == 6:  # Sunday
            continue
        for t in (time(10, 0), time(15, 0)):
            out.append(datetime.combine(d, t, tzinfo=IST).astimezone(UTC))
    return out


async def upsert_slots(db: AsyncSession, school_id: int, today: date) -> None:
    for starts_at in slot_times(today):
        await db.execute(
            insert(VisitSlot)
            .values(
                school_id=school_id,
                starts_at=starts_at,
                capacity=5,
                booked_count=0,
            )
            .on_conflict_do_nothing(index_elements=["school_id", "starts_at"])
        )


async def seed(db: AsyncSession, today: date | None = None) -> dict[str, int]:
    today = today or datetime.now(IST).date()
    school_id = await upsert_school(db)
    await upsert_users(db, school_id)
    await upsert_ad_accounts(db, school_id)
    await upsert_kb(db, school_id)
    await upsert_slots(db, school_id, today)
    counts: dict[str, int] = {}
    for model in (School, User, AdAccount, KbFact, VisitSlot):
        counts[model.__tablename__] = (
            await db.scalar(select(func.count()).select_from(model))
        ) or 0
    return counts


async def main() -> None:
    async with get_sessionmaker()() as db:
        counts = await seed(db)
        await db.commit()
    print("Seeded (fake data):", counts)


if __name__ == "__main__":
    asyncio.run(main())
