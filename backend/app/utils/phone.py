"""Uzbek phone number normalisation."""

from __future__ import annotations

import re


def normalize_uz_phone(raw: str | None) -> str | None:
    """'90 123 45 67', '+998 90 123-45-67', '998901234567' -> '+998901234567'.
    Returns None when the number can't be an Uzbek mobile/landline number."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998") and digits[3] != "0":
        return "+" + digits
    return None
