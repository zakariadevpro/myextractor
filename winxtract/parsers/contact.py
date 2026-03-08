import re

import phonenumbers
from email_validator import EmailNotValidError, validate_email

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_emails(text: str) -> list[str]:
    emails: list[str] = []
    for match in EMAIL_RE.findall(text or ""):
        try:
            validated = validate_email(match, check_deliverability=False)
            emails.append(validated.normalized)
        except EmailNotValidError:
            continue
    return sorted(set(emails))


def extract_phones(text: str, default_region: str = "FR") -> list[str]:
    phones: list[str] = []
    for match in phonenumbers.PhoneNumberMatcher(text or "", default_region):
        if phonenumbers.is_valid_number(match.number):
            phones.append(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))
    return sorted(set(phones))
