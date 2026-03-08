import hashlib

from winxtract.parsers.normalize import normalize_text


def lead_fingerprint(name: str | None, city: str | None, emails: list[str]) -> str:
    if emails:
        base = emails[0].lower()
    else:
        base = f"{(normalize_text(name) or '').lower()}|{(normalize_text(city) or '').lower()}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()
