import re
import unicodedata

# Pre-compiled regex patterns for performance
_RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_RE_WHITESPACE = re.compile(r"\s+")

_COMPANY_SUFFIX_PATTERNS = [
    re.compile(suffix, re.IGNORECASE)
    for suffix in [
        r"\bSAS\b", r"\bSARL\b", r"\bSA\b", r"\bEURL\b",
        r"\bSCI\b", r"\bSNC\b", r"\bSCSP\b", r"\bSEL\b", r"\bSELARL\b",
    ]
]

_ADDRESS_REPLACEMENTS = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in {
        r"\brue\b": "RUE",
        r"\bavenue\b": "AVE",
        r"\bboulevard\b": "BD",
        r"\bplace\b": "PL",
        r"\bchemin\b": "CH",
        r"\broute\b": "RTE",
        r"\bimpasse\b": "IMP",
        r"\ball[ée]e\b": "ALL",
    }.items()
]


def clean_text(text: str) -> str:
    """Clean text by removing special characters and normalizing whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _RE_CONTROL_CHARS.sub("", text)
    text = _RE_WHITESPACE.sub(" ", text).strip()
    return text


def clean_company_name(name: str) -> str:
    """Normalize company name for deduplication comparison."""
    if not name:
        return ""
    name = clean_text(name)
    for pattern in _COMPANY_SUFFIX_PATTERNS:
        name = pattern.sub("", name)
    name = _RE_WHITESPACE.sub(" ", name).strip()
    return name.upper()


def normalize_address(address: str) -> str:
    """Normalize a French address."""
    if not address:
        return ""
    address = clean_text(address)
    for pattern, replacement in _ADDRESS_REPLACEMENTS:
        address = pattern.sub(replacement, address)
    return address.upper()
