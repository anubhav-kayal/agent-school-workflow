"""Leads and their funnel events. Minimum personal data only (DPDP Act)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import Actor, Language, LeadEventType, LeadSource, LeadStatus


class Lead(IdMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("school_id", "source", "external_lead_id"),
        Index("ix_leads_school_created", "school_id", "created_at"),
        Index("ix_leads_school_phone", "school_id", "phone"),
    )

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    source: Mapped[LeadSource] = mapped_column(str_enum(LeadSource, "lead_source"))
    external_lead_id: Mapped[str | None] = mapped_column(String(64))  # Meta lead_id, etc.
    # PII — nulled out by the admin deletion action.
    parent_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164
    email: Mapped[str | None] = mapped_column(String(254))  # optional; enhanced conversions
    grade_interest: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[Language] = mapped_column(str_enum(Language, "language"), default=Language.EN)
    consent: Mapped[bool] = mapped_column(default=False)
    consent_source: Mapped[str | None] = mapped_column(String(100))  # e.g. "meta_form:123"
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[LeadStatus] = mapped_column(
        str_enum(LeadStatus, "lead_status"), default=LeadStatus.NEW
    )
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Attribution (needed for conversion feedback).
    gclid: Mapped[str | None] = mapped_column(String(200))
    campaign_external_id: Mapped[str | None] = mapped_column(String(64))
    ad_set_external_id: Mapped[str | None] = mapped_column(String(64))
    ad_external_id: Mapped[str | None] = mapped_column(String(64))


class LeadEvent(IdMixin, Base):
    __tablename__ = "lead_events"
    __table_args__ = (Index("ix_lead_events_lead_created", "lead_id", "created_at"),)

    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    event: Mapped[LeadEventType] = mapped_column(str_enum(LeadEventType, "lead_event_type"))
    actor: Mapped[Actor] = mapped_column(str_enum(Actor, "actor"))
    note: Mapped[str | None] = mapped_column(Text)
    # e.g. the WhatsApp message id of a counselor button tap; makes replays harmless.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    synced_to_meta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_to_google_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
