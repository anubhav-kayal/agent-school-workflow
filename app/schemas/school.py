from __future__ import annotations

from pydantic import Field

from app.models.enums import AutonomyLevel, Language
from app.schemas.common import Paise, Schema


class SchoolCreate(Schema):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]{2,80}$")
    city: str = Field(min_length=2, max_length=100)
    languages: list[Language] = Field(default_factory=lambda: [Language.EN])
    monthly_budget_cap_paise: Paise | None = None
    daily_budget_cap_paise: Paise | None = None


class SchoolRead(Schema):
    id: int
    name: str
    slug: str
    city: str
    timezone: str
    languages: list[str]
    autonomy_level: AutonomyLevel
    dry_run: bool
    kill_switch: bool
    monthly_budget_cap_paise: int | None
    daily_budget_cap_paise: int | None


class GuardrailConfigRead(Schema):
    max_daily_budget_change_pct: int = Field(ge=0, le=100)
    max_budget_edits_per_ad_set_per_day: int = Field(ge=0)
    min_hours_between_edits: int = Field(ge=0)
