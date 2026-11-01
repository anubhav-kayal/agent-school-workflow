from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import Platform


class AdAccount(IdMixin, TimestampMixin, Base):
    __tablename__ = "ad_accounts"
    __table_args__ = (UniqueConstraint("platform", "external_id"),)

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(str_enum(Platform, "platform"))
    external_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200), default="")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    # Name of the env var holding the credential — never the secret itself.
    credentials_ref: Mapped[str] = mapped_column(String(100))
