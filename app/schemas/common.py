"""Shared Pydantic types."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, ConfigDict, Field
from pydantic import BaseModel as _BaseModel

_DIGITS = re.compile(r"\D+")


def normalize_indian_mobile(raw: str) -> str:
    """Return an Indian mobile number in E.164 (+91XXXXXXXXXX) or raise ValueError."""
    digits = _DIGITS.sub("", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("not a valid Indian mobile number")
    return f"+91{digits}"


IndianMobile = Annotated[str, AfterValidator(normalize_indian_mobile)]
Paise = Annotated[int, Field(ge=0, description="Amount in paise (₹1 = 100 paise)")]


class Schema(_BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)
