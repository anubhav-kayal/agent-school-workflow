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
