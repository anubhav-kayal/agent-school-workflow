from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class KbFact(IdMixin, TimestampMixin, Base):
    """A single verified-or-not fact. Only verified facts may reach parents or ads."""

    __tablename__ = "kb_facts"
    __table_args__ = (UniqueConstraint("school_id", "key"),)

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(50))  # fees, transport, board, results …
    key: Mapped[str] = mapped_column(String(100))  # e.g. fees.class_1
    value: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(default=False, server_default=false())
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
