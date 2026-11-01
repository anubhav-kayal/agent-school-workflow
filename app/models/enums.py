"""Domain enums. Values are what gets stored in the database."""

from enum import StrEnum


class AutonomyLevel(StrEnum):
    L0 = "L0"  # recommend only
    L1 = "L1"  # auto-apply within caps
    L2 = "L2"  # wider caps + auto creatives


class UserRole(StrEnum):
    ADMIN = "admin"
    STRATEGIST = "strategist"
    SCHOOL_VIEWER = "school_viewer"
    SCHOOL_APPROVER = "school_approver"
    COUNSELOR = "counselor"


class Platform(StrEnum):
    META = "meta"
    GOOGLE = "google"


class MetricLevel(StrEnum):
    CAMPAIGN = "campaign"
    AD_SET = "ad_set"  # Google: ad group
    AD = "ad"


class LeadSource(StrEnum):
    META_LEAD_AD = "meta_lead_ad"
    GOOGLE_LEAD_FORM = "google_lead_form"
    WEBSITE = "website"
    WHATSAPP = "whatsapp"
    WALK_IN = "walk_in"


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    HINGLISH = "hinglish"


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    VISIT_BOOKED = "visit_booked"
    VISITED = "visited"
    ADMITTED = "admitted"
    NOT_INTERESTED = "not_interested"


class LeadEventType(StrEnum):
    CREATED = "created"
    CONTACTED = "contacted"
    VISIT_BOOKED = "visit_booked"
    VISITED = "visited"
    ADMITTED = "admitted"
    NOT_INTERESTED = "not_interested"


class Actor(StrEnum):
    ASSISTANT = "assistant"
    COUNSELOR = "counselor"
    SYSTEM = "system"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class BookingStatus(StrEnum):
    BOOKED = "booked"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    NO_SHOW = "no_show"
