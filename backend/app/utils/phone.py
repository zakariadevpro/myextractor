import re

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType, phonenumberutil


def normalize_phone(raw_phone: str, country_code: str = "FR") -> str | None:
    """Normalize a phone number to E.164 format. Returns None if invalid."""
    if not raw_phone:
        return None
    # Clean up common formatting
    cleaned = re.sub(r"[^\d+]", "", raw_phone.strip())
    if not cleaned:
        return None
    try:
        parsed = phonenumbers.parse(cleaned, country_code)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException:
        pass
    return None


def detect_phone_type(raw_phone: str, country_code: str = "FR") -> str:
    """Detect if a phone number is mobile, landline, or unknown."""
    if not raw_phone:
        return "unknown"
    cleaned = re.sub(r"[^\d+]", "", raw_phone.strip())
    try:
        parsed = phonenumbers.parse(cleaned, country_code)
        number_type = phonenumberutil.number_type(parsed)
        if number_type == PhoneNumberType.MOBILE:
            return "mobile"
        elif number_type == PhoneNumberType.FIXED_LINE:
            return "landline"
        elif number_type == PhoneNumberType.FIXED_LINE_OR_MOBILE:
            # French numbers starting with 06/07 are mobile
            national = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            )
            if national.startswith("06") or national.startswith("07"):
                return "mobile"
            return "landline"
    except NumberParseException:
        pass
    return "unknown"


def extract_phones_from_text(text: str) -> list[str]:
    """Extract French phone numbers from text."""
    patterns = [
        r"(?:(?:\+33|0033|0)\s*[1-9])(?:[\s.-]*\d{2}){4}",
        r"\b0[1-9](?:\s?\d{2}){4}\b",
    ]
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        found.extend(matches)
    return list(set(found))
