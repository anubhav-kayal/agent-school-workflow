from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.models.enums import Actor, Language, LeadEventType, LeadSource, LeadStatus
from app.schemas.common import IndianMobile, Schema


class LeadCreate(Schema):
    """Inbound lead from any source. Only the minimum data needed to follow up."""

    source: LeadSource
    external_lead_id: str | None = Field(default=None, max_length=64)
    parent_name: str | None = Field(default=None, max_length=200)
    phone: IndianMobile
    email: EmailStr | None = None
    grade_interest: str | None = Field(default=None, max_length=32)
    language: Language = Language.EN
    consent: bool
    consent_source: str = Field(min_length=1, max_length=100)
    gclid: str | None = Field(default=None, max_length=200)
    campaign_external_id: str | None = None
    ad_set_external_id: str | None = None
    ad_external_id: str | None = None


class LeadRead(Schema):
    id: int
    school_id: int
    source: LeadSource
    parent_name: str | None
    phone: str | None
    grade_interest: str | None
    language: Language
    status: LeadStatus
    consent: bool
    created_at: datetime
    first_response_at: datetime | None
    opted_out_at: datetime | None


class LeadEventCreate(Schema):
    event: LeadEventType
    actor: Actor
    note: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, max_length=128)
