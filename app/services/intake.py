"""Turn external lead events into leads (shared by webhooks/jobs, testable without arq)."""

from __future__ import annotations

import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.meta_leads import MetaLeadClient
from app.models import Lead, School
from app.models.enums import LeadSource
from app.schemas.lead import LeadCreate
from app.services.leads import create_lead

log = logging.getLogger(__name__)


async def ingest_meta_lead(
    db: AsyncSession, client: MetaLeadClient, page_id: str, leadgen_id: str
) -> Lead | None:
    school = await db.scalar(select(School).where(School.meta_page_id == page_id))
    if school is None:
        log.warning("leadgen for unknown page %s", page_id)
        return None
    existing = await db.scalar(
        select(Lead).where(
            Lead.school_id == school.id,
            Lead.source == LeadSource.META_LEAD_AD,
            Lead.external_lead_id == leadgen_id,
        )
    )
    if existing is not None:  # replayed webhook: no second Graph call
        return existing
    meta = await client.fetch_lead(leadgen_id)
    try:
        data = LeadCreate(
            source=LeadSource.META_LEAD_AD,
            external_lead_id=meta.id,
            parent_name=meta.first("full_name", "name"),
            phone=meta.first("phone") or "",
            grade_interest=(meta.first("class", "grade") or "")[:32] or None,
            consent=True,  # submitted a lead form with the school's privacy policy
            consent_source=f"meta_form:{meta.form_id or 'unknown'}",
            campaign_external_id=meta.campaign_id,
            ad_set_external_id=meta.adset_id,
            ad_external_id=meta.ad_id,
        )
    except ValidationError:
        log.warning("meta lead %s has no usable Indian mobile number", leadgen_id)
        return None
    return (await create_lead(db, school.id, data)).lead
