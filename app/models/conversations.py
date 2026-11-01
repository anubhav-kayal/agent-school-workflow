from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import BookingStatus, Direction


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), unique=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|escalated|closed
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 24h window


class Message(IdMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[Direction] = mapped_column(str_enum(Direction, "direction"))
    kind: Mapped[str] = mapped_column(String(16))  # text|template|interactive|button_reply
    body: Mapped[str | None] = mapped_column(Text)
    template_name: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)  # dedupe
    status: Mapped[str] = mapped_column(String(16), default="queued")


class VisitSlot(IdMixin, TimestampMixin, Base):
    __tablename__ = "visit_slots"
    __table_args__ = (
        UniqueConstraint("school_id", "starts_at"),
        CheckConstraint("booked_count >= 0 AND booked_count <= capacity", name="within_capacity"),
    )

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    booked_count: Mapped[int] = mapped_column(Integer, default=0)


class VisitBooking(IdMixin, TimestampMixin, Base):
    __tablename__ = "visit_bookings"

    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("visit_slots.id"), index=True)
    status: Mapped[BookingStatus] = mapped_column(
        str_enum(BookingStatus, "booking_status"), default=BookingStatus.BOOKED
    )
    reminder_day_before_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_morning_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
