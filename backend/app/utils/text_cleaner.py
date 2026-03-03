import re
import unicodedata


def clean_text(text: str) -> str:
    """Clean text by removing special characters and normalizing whitespace."""
    if not text:
        return ""
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_company_name(name: str) -> str:
    """Normalize company name for deduplication comparison."""
    if not name:
        return ""
    name = clean_text(name)
    # Remove common suffixes
    suffixes = [
        r"\bSAS\b",
        r"\bSARL\b",
        r"\bSA\b",
        r"\bEURL\b",
        r"\bSCI\b",
        r"\bSNC\b",
        r"\bSCSP\b",
        r"\bSEL\b",
        r"\bSELARL\b",
    ]
    for suffix in suffixes:
        name = re.sub(suffix, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name.upper()


def normalize_address(address: str) -> str:
    """Normalize a French address."""
    if not address:
        return ""
    address = clean_text(address)
    # Common abbreviations
    replacements = {
        r"\brue\b": "RUE",
        r"\bavenue\b": "AVE",
        r"\bboulevard\b": "BD",
        r"\bplace\b": "PL",
        r"\bchemin\b": "CH",
        r"\broute\b": "RTE",
        r"\bimpasse\b": "IMP",
        r"\ballée\b": "ALL",
    }
    for pattern, replacement in replacements.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
    return address.upper()
