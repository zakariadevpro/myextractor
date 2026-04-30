import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Common disposable email domains to flag
DISPOSABLE_DOMAINS = {
    "guerrillamail.com",
    "guerrillamailblock.com",
    "mailinator.com",
    "tempmail.com",
    "throwaway.email",
    "yopmail.com",
    "sharklasers.com",
    "10minutemail.com",
    "getnada.com",
    "trashmail.com",
    "fakemailgenerator.com",
    "maildrop.cc",
    "dispostable.com",
}

# Domains that scrapers commonly pick up from template strings or doc examples.
PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.fr",
    "example.org",
    "exemple.com",
    "exemple.fr",
    "test.com",
    "test.fr",
    "domain.com",
    "email.com",
    "yourdomain.com",
    "votredomaine.com",
    "monsite.com",
    "monsite.fr",
}

# Local-parts that are obviously placeholders rather than real mailbox names.
PLACEHOLDER_LOCAL_PARTS = {
    "email",
    "yourname",
    "your-name",
    "votre-email",
    "votreemail",
    "votrenom",
    "name",
    "nom",
    "prenom",
    "firstname",
    "lastname",
    "user",
    "username",
    "test",
    "exemple",
    "example",
    "demo",
    "xxx",
    "abc",
    "azerty",
    "qwerty",
}


def is_valid_email(email: str) -> bool:
    """Validate email syntax + reject placeholders/disposables.

    Levels covered: regex syntax + placeholder domain/local detection +
    disposable mailbox domain blacklist. Does NOT do DNS/MX or SMTP probe.
    """
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
    if domain in PLACEHOLDER_DOMAINS:
        return False
    if local_part in PLACEHOLDER_LOCAL_PARTS:
        return False
    if len(set(local_part)) == 1 and len(local_part) >= 3:
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
