from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, false, true
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import AutonomyLevel


class School(IdMixin, TimestampMixin, Base):
    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    city: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=lambda: ["en"])
    autonomy_level: Mapped[AutonomyLevel] = mapped_column(
        str_enum(AutonomyLevel, "autonomy_level"), default=AutonomyLevel.L0, server_default="L0"
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Money in integer paise.
    monthly_budget_cap_paise: Mapped[int | None] = mapped_column(BigInteger)
    daily_budget_cap_paise: Mapped[int | None] = mapped_column(BigInteger)
    monthly_llm_budget_usd: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Webhook routing: which Facebook page / WhatsApp number belongs to this school.
    meta_page_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    brand: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # logo path, colours

    guardrails: Mapped[GuardrailConfig | None] = relationship(
        back_populates="school", uselist=False, cascade="all, delete-orphan"
    )


class GuardrailConfig(IdMixin, TimestampMixin, Base):
    """Per-school guardrail overrides. Defaults mirror the documented policy."""

    __tablename__ = "guardrail_configs"

    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), unique=True
    )
    max_daily_budget_change_pct: Mapped[int] = mapped_column(Integer, default=20)
    max_budget_edits_per_ad_set_per_day: Mapped[int] = mapped_column(Integer, default=1)
    min_hours_between_edits: Mapped[int] = mapped_column(Integer, default=24)

    school: Mapped[School] = relationship(back_populates="guardrails")
