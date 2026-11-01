"""Website enquiry form → lead → first-response job (template, no LLM)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.jobs.queue import Enqueuer, get_enqueuer
from app.models import School
from app.models.enums import Language, LeadSource
from app.schemas.common import IndianMobile, Schema
from app.schemas.lead import LeadCreate
from app.services.leads import create_lead

router = APIRouter(prefix="/webhooks/forms", tags=["webhooks"])


class WebsiteEnquiry(Schema):
    parent_name: str = Field(min_length=1, max_length=200)
    phone: IndianMobile
    grade_interest: str = Field(min_length=1, max_length=32)
    language: Language = Language.EN
    consent: bool
    form_id: str = Field(default="website", max_length=60)
    gclid: str | None = Field(default=None, max_length=200)


@router.post("/{school_slug}", status_code=status.HTTP_202_ACCEPTED)
async def website_enquiry(
    school_slug: str,
    body: WebsiteEnquiry,
    db: Annotated[AsyncSession, Depends(get_session)],
    enqueue: Annotated[Enqueuer, Depends(get_enqueuer)],
) -> dict[str, Any]:
    if not body.consent:
        raise HTTPException(422, "consent is required to contact the parent")
    school = await db.scalar(select(School).where(School.slug == school_slug))
    if school is None:
        raise HTTPException(404, "unknown school")
    data = LeadCreate(
        source=LeadSource.WEBSITE,
        parent_name=body.parent_name,
        phone=body.phone,
        grade_interest=body.grade_interest,
        language=body.language,
        consent=True,
        consent_source=f"website:{body.form_id}",
        gclid=body.gclid,
    )
    result = await create_lead(db, school.id, data)
    await db.commit()
    await enqueue("send_first_response", job_id=f"first:{result.lead.id}", lead_id=result.lead.id)
    return {"lead_id": result.lead.id, "created": result.created}
