from datetime import UTC, datetime

import pytest

from app.formatting import format_inr, format_inr_short, format_slot, group_indian


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0"),
        (999, "999"),
        (1000, "1,000"),
        (100000, "1,00,000"),
        (1500000, "15,00,000"),
        (123456789, "12,34,56,789"),
        (-150000, "-1,50,000"),
    ],
)
def test_group_indian(n: int, expected: str) -> None:
    assert group_indian(n) == expected


def test_format_inr_rounds_paise() -> None:
    assert format_inr(150_000_00) == "₹1,50,000"
    assert format_inr(85_000_50) == "₹85,001"
    assert format_inr(0) == "₹0"


@pytest.mark.parametrize(
    ("paise", "expected"),
    [
        (150_000_00, "₹1.5 lakh"),
        (100_000_00, "₹1 lakh"),
        (2_25_00_000_00, "₹2.25 crore"),
        (45_000_00, "₹45,000"),
    ],
)
def test_format_inr_short(paise: int, expected: str) -> None:
    assert format_inr_short(paise) == expected


def test_format_slot_in_ist_and_fits_button() -> None:
    slot = datetime(2026, 11, 7, 4, 30, tzinfo=UTC)  # 10:00 IST Saturday
    assert format_slot(slot) == "Sat 7 Nov, 10:00 AM"
    hindi = format_slot(slot, "hi")
    assert hindi == "शनि 7 नव, 10:00"
    assert len(format_slot(slot)) <= 20 and len(hindi) <= 20


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError):
        format_slot(datetime(2026, 11, 7, 10, 0))
