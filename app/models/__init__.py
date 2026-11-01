"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.models.ad_account import AdAccount
from app.models.ads import Ad, AdSet, Campaign
from app.models.base import Base
from app.models.metrics import MetricsDaily, MetricsHourly
from app.models.school import GuardrailConfig, School
from app.models.user import User

__all__ = [
    "Ad",
    "AdAccount",
    "AdSet",
    "Base",
    "Campaign",
    "GuardrailConfig",
    "MetricsDaily",
    "MetricsHourly",
    "School",
    "User",
]
