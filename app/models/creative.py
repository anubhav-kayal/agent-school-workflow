from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import CreativeStatus, Language


class Creative(IdMixin, TimestampMixin, Base):
    __tablename__ = "creatives"
    __table_args__ = (Index("ix_creatives_school_status", "school_id", "status"),)

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    grade: Mapped[str] = mapped_column(String(32))
    angle: Mapped[str] = mapped_column(String(64))
    language: Mapped[Language] = mapped_column(str_enum(Language, "language"))
    primary_text: Mapped[str] = mapped_column(Text)
    headline: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(255))
    cta: Mapped[str] = mapped_column(String(32))
    claims_used: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)  # kb_facts ids
    image_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[CreativeStatus] = mapped_column(
        str_enum(CreativeStatus, "creative_status"), default=CreativeStatus.DRAFT
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
