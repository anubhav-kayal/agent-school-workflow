"""Agent runs, the actions they propose, and the audit trail of every executor decision."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import ActionStatus, ActionType


class AgentRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_school_created", "school_id", "created_at"),)

    agent: Mapped[str] = mapped_column(String(32))
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok|error|skipped|batched
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    cost_inr: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    batch_id: Mapped[str | None] = mapped_column(String(100))
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class ProposedAction(IdMixin, TimestampMixin, Base):
    __tablename__ = "proposed_actions"
    __table_args__ = (Index("ix_proposed_actions_school_status", "school_id", "status"),)

    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    type: Mapped[ActionType] = mapped_column(str_enum(ActionType, "action_type"))
    target: Mapped[str | None] = mapped_column(String(100))  # e.g. "meta:ad_set:123"
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    expected_effect: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ActionStatus] = mapped_column(
        str_enum(ActionStatus, "action_status"), default=ActionStatus.PENDING
    )
    block_reason: Mapped[str | None] = mapped_column(Text)  # the rule that blocked it
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(IdMixin, Base):
    """Append-only. One row per executor decision, applied or not."""

    __tablename__ = "audit_log"

    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id", ondelete="SET NULL"))
    actor: Mapped[str] = mapped_column(String(100))  # "executor", "user:12", "agent:optimizer"
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(100))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dry_run: Mapped[bool] = mapped_column()
    proposed_action_id: Mapped[int | None] = mapped_column(
        ForeignKey("proposed_actions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Report(IdMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("school_id", "period_start", "language"),)

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    language: Mapped[str] = mapped_column(String(16), default="en")
    body_md: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
