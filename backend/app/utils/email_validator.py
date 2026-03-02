import re

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Common disposable email domains to flag
DISPOSABLE_DOMAINS = {
    "guerrillamail.com", "mailinator.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com",
}


def is_valid_email(email: str) -> bool:
    """Validate email syntax. Returns True if valid."""
    if not email:
        return False
    email = email.strip().lower()
    if len(email) > 254:
        return False
    local_part, sep, domain = email.partition("@")
    if not sep:
        return False
    if len(local_part) > 64 or len(domain) > 255:
        return False
    if not EMAIL_REGEX.match(email):
        return False
    if domain in DISPOSABLE_DOMAINS:
        return False
    return True


def extract_emails_from_text(text: str) -> list[str]:
    """Extract all email addresses from a text string."""
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    found = re.findall(pattern, text)
    # Deduplicate and lowercase
    seen = set()
    unique = []
    for email in found:
        lower = email.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(lower)
    return unique
