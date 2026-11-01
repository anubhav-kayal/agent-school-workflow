import pytest
from pydantic import ValidationError

from app.models.enums import LeadSource
from app.schemas.common import normalize_indian_mobile
from app.schemas.kb import KbFactUpsert
from app.schemas.lead import LeadCreate
from app.schemas.school import SchoolCreate


@pytest.mark.parametrize(
    "raw",
    ["9999900001", "+91 99999 00001", "09999900001", "919999900001", "+91-99999-00001"],
)
def test_indian_mobile_normalized(raw: str) -> None:
    assert normalize_indian_mobile(raw) == "+919999900001"


@pytest.mark.parametrize("raw", ["12345", "5999900001", "+1 415 555 0100", ""])
def test_invalid_mobile_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_indian_mobile(raw)


def lead_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source": "website",
        "phone": "99999 00001",
        "consent": True,
        "consent_source": "website_form:v1",
    }
    return {**base, **overrides}


def test_lead_create_normalizes_phone() -> None:
    lead = LeadCreate.model_validate(lead_payload())
    assert lead.phone == "+919999900001"
    assert lead.source is LeadSource.WEBSITE


def test_lead_create_requires_consent_fields() -> None:
    with pytest.raises(ValidationError):
        LeadCreate.model_validate({"source": "website", "phone": "9999900001"})


def test_lead_create_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LeadCreate.model_validate(lead_payload(aadhaar="0000"))  # never collect extra PII


def test_school_money_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        SchoolCreate(name="Demo", slug="demo", city="Pune", daily_budget_cap_paise=-1)


def test_kb_key_format() -> None:
    assert KbFactUpsert(topic="fees", key="fees.class_1", value="₹85,000").key == "fees.class_1"
    with pytest.raises(ValidationError):
        KbFactUpsert(topic="fees", key="Fees Class 1", value="x")
