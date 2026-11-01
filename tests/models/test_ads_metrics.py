from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdAccount, AdSet, Campaign, MetricsHourly, School
from app.models.enums import MetricLevel, Platform

HOUR = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)


async def make_campaign(db: AsyncSession) -> Campaign:
    school = School(name="Demo", slug="demo-ads", city="Pune")
    db.add(school)
    await db.flush()
    account = AdAccount(
        school_id=school.id,
        platform=Platform.META,
        external_id="act_1",
        credentials_ref="META_SYSTEM_USER_TOKEN",
    )
    db.add(account)
    await db.flush()
    campaign = Campaign(
        school_id=school.id,
        ad_account_id=account.id,
        platform=Platform.META,
        external_id="c1",
        name="Nursery | Lead",
        status="ACTIVE",
    )
    db.add(campaign)
    await db.flush()
    return campaign


async def test_ad_set_external_id_unique(db: AsyncSession) -> None:
    c = await make_campaign(db)
    for _ in range(2):
        db.add(
            AdSet(
                school_id=c.school_id,
                campaign_id=c.id,
                platform=Platform.META,
                external_id="as1",
                name="Nursery 3km",
                status="ACTIVE",
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_hourly_metrics_upsert_is_idempotent(db: AsyncSession) -> None:
    c = await make_campaign(db)
    row = {
        "school_id": c.school_id,
        "platform": Platform.META,
        "level": MetricLevel.AD_SET,
        "external_id": "as1",
        "hour": HOUR,
        "spend_paise": 50_000,
        "leads": 2,
    }
    for spend in (50_000, 65_000):  # second pull restates the same hour
        stmt = insert(MetricsHourly).values(**{**row, "spend_paise": spend})
        stmt = stmt.on_conflict_do_update(
            index_elements=["platform", "level", "external_id", "hour"],
            set_={"spend_paise": stmt.excluded.spend_paise, "leads": stmt.excluded.leads},
        )
        await db.execute(stmt)
    count = await db.scalar(select(func.count()).select_from(MetricsHourly))
    spend_now = await db.scalar(select(MetricsHourly.spend_paise))
    assert (count, spend_now) == (1, 65_000)
