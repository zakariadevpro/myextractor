import re
from typing import Any
from urllib.parse import urlparse

from winxtract.core.models import LeadData
from winxtract.parsers.contact import EMAIL_RE

_PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "yahoo.com",
    "yahoo.fr",
    "icloud.com",
    "protonmail.com",
    "orange.fr",
    "free.fr",
    "laposte.net",
    "sfr.fr",
    "bbox.fr",
}

_BUSINESS_HINTS = {
    "sarl",
    "sas",
    "sasu",
    "sa",
    "eurl",
    "scop",
    "scp",
    "association",
    "auto-ecole",
    "cabinet",
    "atelier",
    "garage",
    "pharmacie",
    "boulangerie",
    "restaurant",
    "hotel",
    "coiffure",
    "immobilier",
    "entreprise",
    "services",
    "commerce",
}

_PHONE_LIKE_RE = re.compile(r"(?:\+?\d[\d\.\-\s\(\)]{7,}\d)")


def _profile_defaults(profile: str | None) -> dict[str, bool]:
    normalized = (profile or "").strip().lower()
    if normalized in {"b2c_etendu", "particulier_etendu"}:
        return {
            "drop_person_records": False,
            "drop_private_email_records": False,
            "redact_name": False,
            "redact_contact": True,
            "redact_address": False,
            "redact_page_url": False,
            "sanitize_description": True,
        }
    # default profile: strict B2C compliance
    return {
        "drop_person_records": True,
        "drop_private_email_records": True,
        "redact_name": True,
        "redact_contact": True,
        "redact_address": True,
        "redact_page_url": True,
        "sanitize_description": True,
    }


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def is_particulier_conforme_mode(source_params: dict[str, Any] | None) -> bool:
    if not source_params:
        return False
    mode = str(source_params.get("privacy_mode", "none")).strip().lower()
    profile = str(source_params.get("privacy_profile", "")).strip().lower()
    return mode in {"particulier_conforme", "particulier", "private_compliant"} or profile in {
        "b2c_conforme",
        "b2c_etendu",
        "particulier_conforme",
        "particulier_etendu",
    }


def looks_like_person_name(value: str | None) -> bool:
    if not value:
        return False
    cleaned = value.strip()
    if not cleaned or any(ch.isdigit() for ch in cleaned):
        return False
    lowered = cleaned.lower()
    if any(hint in lowered for hint in _BUSINESS_HINTS):
        return False
    tokens = [t for t in re.split(r"[\s\-']+", cleaned) if t]
    if not 2 <= len(tokens) <= 4:
        return False
    alphabetic_tokens = [t for t in tokens if re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", t)]
    if len(alphabetic_tokens) != len(tokens):
        return False
    return all(t[0].isupper() for t in tokens if t)


def has_private_email_domain(emails: list[str]) -> bool:
    for email in emails:
        domain = email.split("@")[-1].lower().strip()
        if domain in _PERSONAL_EMAIL_DOMAINS:
            return True
    return False


def sanitize_text_sensitive(text: str | None) -> str | None:
    if not text:
        return text
    redacted = EMAIL_RE.sub("[redacted-email]", text)
    redacted = _PHONE_LIKE_RE.sub("[redacted-phone]", redacted)
    return redacted


def to_domain_only_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def apply_particulier_conforme_policy(
    lead: LeadData,
    *,
    source_params: dict[str, Any] | None,
) -> LeadData | None:
    if not is_particulier_conforme_mode(source_params):
        return lead

    params = source_params or {}
    defaults = _profile_defaults(str(params.get("privacy_profile", "")))
    drop_person_records = _parse_bool(params.get("privacy_drop_person_records"), defaults["drop_person_records"])
    drop_private_email_records = _parse_bool(
        params.get("privacy_drop_private_email_records"),
        defaults["drop_private_email_records"],
    )
    redact_name = _parse_bool(params.get("privacy_redact_name"), defaults["redact_name"])
    redact_contact = _parse_bool(params.get("privacy_redact_contact"), defaults["redact_contact"])
    redact_address = _parse_bool(params.get("privacy_redact_address"), defaults["redact_address"])
    redact_page_url = _parse_bool(params.get("privacy_redact_page_url"), defaults["redact_page_url"])
    sanitize_description = _parse_bool(params.get("privacy_sanitize_description"), defaults["sanitize_description"])

    is_person_name = looks_like_person_name(lead.name)
    if drop_person_records and is_person_name:
        return None

    if drop_private_email_records and has_private_email_domain(lead.emails):
        return None

    if redact_name and is_person_name:
        lead.name = None

    if redact_contact:
        lead.emails = []
        lead.phones = []

    if redact_address:
        lead.address = None

    if redact_page_url:
        lead.page_url = to_domain_only_url(lead.page_url)

    if sanitize_description:
        lead.description = sanitize_text_sensitive(lead.description)

    return lead
