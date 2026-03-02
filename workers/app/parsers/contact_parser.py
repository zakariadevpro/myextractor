import re


def extract_emails(html_or_text: str) -> list[str]:
    """Extract email addresses from HTML or text content."""
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    found = re.findall(pattern, html_or_text)

    # Deduplicate and filter out common false positives
    exclude_patterns = {"@sentry", "@example", "@test", "wixpress", "googleapis"}
    seen = set()
    result = []
    for email in found:
        lower = email.lower()
        if lower in seen:
            continue
        if any(exc in lower for exc in exclude_patterns):
            continue
        if len(lower) > 254:
            continue
        seen.add(lower)
        result.append(lower)

    return result


def extract_phones(html_or_text: str) -> list[str]:
    """Extract French phone numbers from HTML or text content."""
    patterns = [
        r"(?:\+33|0033|0)\s*[1-9](?:[\s.-]*\d{2}){4}",
        r"\b0[1-9]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\b",
    ]

    found = []
    for pattern in patterns:
        matches = re.findall(pattern, html_or_text)
        found.extend(matches)

    # Clean and deduplicate
    cleaned = set()
    result = []
    for phone in found:
        normalized = re.sub(r"[\s.-]", "", phone)
        if normalized not in cleaned and len(normalized) >= 10:
            cleaned.add(normalized)
            result.append(phone.strip())

    return result
