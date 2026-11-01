from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import Schema


class KbFactUpsert(Schema):
    topic: str = Field(pattern=r"^[a-z_]{2,50}$")
    key: str = Field(pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)+$", max_length=100)  # fees.class_1
    value: str = Field(min_length=1, max_length=2000)


class KbFactRead(Schema):
    id: int
    topic: str
    key: str
    value: str
    verified: bool
    updated_at: datetime
