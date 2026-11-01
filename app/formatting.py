"""School-facing formatting: Indian rupees and IST dates. All inputs are paise / UTC."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

_EN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_HI_DAYS = ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"]
_EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_HI_MONTHS = ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुला", "अग", "सित", "अक्टू", "नव", "दिस"]


def group_indian(n: int) -> str:
    """1500000 -> '15,00,000' (last three digits, then pairs)."""
    sign, digits = ("-", str(-n)) if n < 0 else ("", str(n))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    pairs: list[str] = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return sign + ",".join([head, *pairs, tail])


def format_inr(paise: int) -> str:
    """Rounded to whole rupees: 15000000 paise -> '₹1,50,000'."""
    rupees = int((Decimal(paise) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return f"₹{group_indian(rupees)}"


def format_inr_short(paise: int) -> str:
    """Compact form for prose: '₹1.5 lakh', '₹2.25 crore', '₹45,000'."""
    rupees = Decimal(paise) / 100
    for size, unit in ((Decimal(10_000_000), "crore"), (Decimal(100_000), "lakh")):
        if abs(rupees) >= size:
            value = (rupees / size).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).normalize()
            return f"₹{value:f} {unit}"
    return format_inr(paise)


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime; store and pass UTC-aware datetimes")
    return dt.astimezone(IST)


def format_slot(dt: datetime, language: str = "en") -> str:
    """Short slot label that fits a WhatsApp button (≤ 20 chars): 'Sat 7 Nov, 10:00 AM'."""
    local = to_ist(dt)
    if language == "hi":
        return (
            f"{_HI_DAYS[local.weekday()]} {local.day} {_HI_MONTHS[local.month - 1]}, {local:%H:%M}"
        )
    hour = local.strftime("%I:%M %p").lstrip("0")
    return f"{_EN_DAYS[local.weekday()]} {local.day} {_EN_MONTHS[local.month - 1]}, {hour}"
