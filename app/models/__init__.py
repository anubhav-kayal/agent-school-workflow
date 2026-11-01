"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.models.ad_account import AdAccount
from app.models.base import Base
from app.models.school import GuardrailConfig, School
from app.models.user import User

__all__ = ["AdAccount", "Base", "GuardrailConfig", "School", "User"]
