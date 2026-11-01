"""Cross-table integrity: cascades for data deletion and migration/model drift."""

import asyncio
import os
import sys
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import (
    Conversation,
    Lead,
    LeadEvent,
    Message,
    School,
    VisitBooking,
    VisitSlot,
)
from app.models.enums import Actor, Direction, LeadEventType, LeadSource
from tests.conftest import TEST_DATABASE_URL

NOW = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)


async def lead_with_history(db: AsyncSession) -> tuple[Lead, VisitSlot]:
    school = School(name="Demo", slug="demo-integrity", city="Pune")
    db.add(school)
    await db.flush()
    lead = Lead(school_id=school.id, source=LeadSource.WEBSITE, phone="+919999900003")
    slot = VisitSlot(school_id=school.id, starts_at=NOW, capacity=5, booked_count=1)
    db.add_all([lead, slot])
    await db.flush()
    conv = Conversation(lead_id=lead.id, school_id=school.id)
    db.add(conv)
    await db.flush()
    db.add_all(
        [
            Message(
                conversation_id=conv.id, direction=Direction.INBOUND, kind="text", body="Fees?"
            ),
            LeadEvent(
                lead_id=lead.id,
                school_id=school.id,
                event=LeadEventType.CREATED,
                actor=Actor.SYSTEM,
            ),
            VisitBooking(lead_id=lead.id, slot_id=slot.id),
        ]
    )
    await db.flush()
    return lead, slot


async def count(db: AsyncSession, model: type) -> int:
    return (await db.scalar(select(func.count()).select_from(model))) or 0


async def test_hard_deleting_lead_removes_all_personal_history(db: AsyncSession) -> None:
    lead, _ = await lead_with_history(db)
    await db.execute(text("DELETE FROM leads WHERE id = :id"), {"id": lead.id})
    for model in (Conversation, Message, LeadEvent, VisitBooking):
        assert await count(db, model) == 0, model.__tablename__


async def test_slot_with_bookings_cannot_be_deleted(db: AsyncSession) -> None:
    _, slot = await lead_with_history(db)
    with pytest.raises(IntegrityError):
        await db.execute(text("DELETE FROM visit_slots WHERE id = :id"), {"id": slot.id})


async def test_migrations_match_models() -> None:
    """Apply migrations to a scratch database and assert no autogenerate drift."""
    scratch = "admissionpilot_migcheck"
    admin = create_async_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {scratch}"))
        await conn.execute(text(f"CREATE DATABASE {scratch}"))
    url = TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{scratch}"
    env = {**os.environ, "DATABASE_URL": url}
    try:
        for args in (["upgrade", "head"], ["check"], ["downgrade", "base"]):
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "alembic", *args, env=env, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            assert proc.returncode == 0, stderr.decode()
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)"))
        await admin.dispose()
