"""Local mirrors of platform objects (campaigns, ad sets / ad groups, ads)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import Platform


class PlatformObjectMixin(IdMixin, TimestampMixin):
    @declared_attr.directive
    def __table_args__(cls) -> tuple[UniqueConstraint, ...]:
        return (UniqueConstraint("platform", "external_id"),)

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(str_enum(Platform, "platform"))
    external_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(32))  # platform status string, as reported
    daily_budget_paise: Mapped[int | None] = mapped_column(BigInteger)
    # Targeting labels parsed from naming convention or set by Creative studio.
    grade: Mapped[str | None] = mapped_column(String(32))
    angle: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(16))
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Campaign(PlatformObjectMixin, Base):
    __tablename__ = "campaigns"

    ad_account_id: Mapped[int] = mapped_column(
        ForeignKey("ad_accounts.id", ondelete="CASCADE"), index=True
    )
    objective: Mapped[str | None] = mapped_column(String(64))


class AdSet(PlatformObjectMixin, Base):
    __tablename__ = "ad_sets"

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    learning_stage: Mapped[str | None] = mapped_column(String(32))  # e.g. LEARNING, SUCCESS


class Ad(PlatformObjectMixin, Base):
    __tablename__ = "ads"

    ad_set_id: Mapped[int] = mapped_column(ForeignKey("ad_sets.id", ondelete="CASCADE"), index=True)
    effective_status: Mapped[str | None] = mapped_column(String(32))  # e.g. DISAPPROVED
