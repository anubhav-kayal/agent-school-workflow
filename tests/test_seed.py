from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KbFact, User
from app.seed import seed, slot_times

IST = ZoneInfo("Asia/Kolkata")


async def test_seed_is_idempotent(db: AsyncSession) -> None:
    first = await seed(db, today=date(2026, 11, 2))
    second = await seed(db, today=date(2026, 11, 2))
    assert first == second
    assert first["schools"] == 1
    assert first["users"] == 5


async def test_seed_has_unverified_fact_and_only_fake_contacts(db: AsyncSession) -> None:
    await seed(db, today=date(2026, 11, 2))
    unverified = (await db.scalars(select(KbFact).where(KbFact.verified.is_(False)))).all()
    assert [f.key for f in unverified] == ["results.class_10_2026"]
    for user in (await db.scalars(select(User))).all():
        assert user.email.endswith("@example.test")
        assert user.whatsapp_number is None or user.whatsapp_number.startswith("+9199999")


def test_slots_skip_sundays_and_use_ist() -> None:
    slots = slot_times(date(2026, 11, 2), days=7)  # Mon 2 Nov → next 7 days
    local = [s.astimezone(IST) for s in slots]
    assert all(s.weekday() != 6 for s in local)
    assert {s.hour for s in local} == {10, 15}
    assert len(slots) == 12  # 6 working days x 2
