"""Verified knowledge base access. Unverified facts never leave this module."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KbFact


@dataclass(frozen=True)
class Fact:
    id: int
    topic: str
    key: str
    value: str


async def verified_facts(db: AsyncSession, school_id: int, topic: str | None = None) -> list[Fact]:
    stmt = select(KbFact).where(KbFact.school_id == school_id, KbFact.verified.is_(True))
    if topic:
        stmt = stmt.where(KbFact.topic == topic.strip().lower())
    rows = (await db.scalars(stmt.order_by(KbFact.topic, KbFact.key))).all()
    return [Fact(r.id, r.topic, r.key, r.value) for r in rows]


async def topics(db: AsyncSession, school_id: int) -> list[str]:
    stmt = select(KbFact.topic).where(KbFact.school_id == school_id).distinct()
    return sorted((await db.scalars(stmt)).all())


def kb_prompt_block(facts: list[Fact]) -> str:
    """Byte-stable serialisation for the cached prompt prefix (sorted, no timestamps)."""
    rows = [
        {"id": f.id, "key": f.key, "value": f.value} for f in sorted(facts, key=lambda f: f.key)
    ]
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
