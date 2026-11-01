"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.models.ad_account import AdAccount
from app.models.ads import Ad, AdSet, Campaign
from app.models.agents import AgentRun, AuditLog, ProposedAction, Report
from app.models.base import Base
from app.models.conversations import Conversation, Message, VisitBooking, VisitSlot
from app.models.creative import Creative
from app.models.kb import KbFact
from app.models.leads import Lead, LeadEvent
from app.models.metrics import MetricsDaily, MetricsHourly
from app.models.school import GuardrailConfig, School
from app.models.user import User

__all__ = [
    "Ad",
    "AdAccount",
    "AdSet",
    "AgentRun",
    "AuditLog",
    "Base",
    "Campaign",
    "Conversation",
    "Creative",
    "GuardrailConfig",
    "KbFact",
    "Lead",
    "LeadEvent",
    "Message",
    "MetricsDaily",
    "MetricsHourly",
    "ProposedAction",
    "Report",
    "School",
    "User",
    "VisitBooking",
    "VisitSlot",
]
