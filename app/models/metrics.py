"""Delivery metrics. Hourly rows are upserted by the sync job; daily rows are rollups.

Funnel outcomes (visits, admissions) are NOT stored here; they come from lead_events and
are joined in metrics/kpis.py so cost per visit / admission is always computed in code.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import MetricLevel, Platform


class DeliveryMetricsMixin(IdMixin, TimestampMixin):
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    platform: Mapped[Platform] = mapped_column(str_enum(Platform, "platform"))
    level: Mapped[MetricLevel] = mapped_column(str_enum(MetricLevel, "metric_level"))
    external_id: Mapped[str] = mapped_column(String(64))
    spend_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    leads: Mapped[int] = mapped_column(BigInteger, default=0)  # platform-reported leads
    reach: Mapped[int | None] = mapped_column(BigInteger)
    frequency: Mapped[float | None] = mapped_column(Numeric(8, 4))
    ctr: Mapped[float | None] = mapped_column(Numeric(8, 6))  # as reported, fraction


class MetricsHourly(DeliveryMetricsMixin, Base):
    __tablename__ = "metrics_hourly"

    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # start of hour, UTC

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Index, ...]:
        return (
            Index("uq_metrics_hourly_key", "platform", "level", "external_id", "hour", unique=True),
            Index("ix_metrics_hourly_school_hour", "school_id", "hour"),
        )


class MetricsDaily(DeliveryMetricsMixin, Base):
    __tablename__ = "metrics_daily"

    day: Mapped[date] = mapped_column(Date)  # calendar day in the school's timezone

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Index, ...]:
        return (
            Index("uq_metrics_daily_key", "platform", "level", "external_id", "day", unique=True),
            Index("ix_metrics_daily_school_day", "school_id", "day"),
        )
