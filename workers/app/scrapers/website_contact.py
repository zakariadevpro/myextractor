import asyncio
import logging
import re
from collections import deque
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.parsers.contact_parser import extract_emails
from app.scrapers.base import ScrapedLead
from app.scrapers.resilience import pick_user_agent

logger = logging.getLogger(__name__)

CONTACT_LINK_HINTS = {
    "contact",
    "contactez",
    "contacter",
    "nous-contacter",
    "mentions",
    "legales",
    "legal",
    "impressum",
    "about",
    "a-propos",
    "equipe",
}

DEFAULT_CONTACT_PATHS = (
    "/contact",
    "/contactez-nous",
    "/nous-contacter",
    "/contacts",
    "/mentions-legales",
)

IGNORED_EMAIL_PARTS = {
    "@example.",
    "@test.",
    "@sentry",
    "wixpress",
    "googleapis",
    "schema.org",
    "domain.com",
    "email.com",
}


def normalize_website_url(raw_url: str | None) -> str | None:
    candidate = (raw_url or "").strip()
    if not candidate:
        return None
    if candidate.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    if not re.match(r"^https?://", candidate, flags=re.IGNORECASE):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc or "." not in parsed.netloc:
        return None

    scheme = parsed.scheme.lower() if parsed.scheme in {"http", "https"} else "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return f"{scheme}://{netloc}{path}"


def _same_site(url: str, base_url: str) -> bool:
    parsed = urlparse(url)
    base = urlparse(base_url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == base.netloc.lower()


def _decode_cf_email(encoded: str) -> str | None:
    try:
        key = int(encoded[:2], 16)
        chars = [
            chr(int(encoded[index : index + 2], 16) ^ key)
            for index in range(2, len(encoded), 2)
        ]
        value = "".join(chars).strip().lower()
        return value if "@" in value else None
    except Exception:
        return None


def _deobfuscate_email_text(text: str) -> str:
    value = unquote(text or "")
    replacements = [
        (r"\s*(?:\[at\]|\(at\)|\bat\b)\s*", "@"),
        (r"\s*(?:\[arobase\]|\(arobase\)|\barobase\b)\s*", "@"),
        (r"\s*(?:\[dot\]|\(dot\)|\bdot\b)\s*", "."),
        (r"\s*(?:\[point\]|\(point\)|\bpoint\b)\s*", "."),
    ]
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return value


def _clean_emails(emails: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for email in emails:
        value = email.strip().strip(".,;:()[]{}<>").lower()
        if not value or value in seen:
            continue
        if any(part in value for part in IGNORED_EMAIL_PARTS):
            continue
        if len(value) > 254:
            continue
        seen.add(value)
        result.append(value)
    return result[:5]


def extract_emails_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    emails: list[str] = []

    for element in soup.select("script, style, noscript, svg"):
        element.decompose()

    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        if href.startswith("mailto:"):
            emails.extend(extract_emails(unquote(href.removeprefix("mailto:"))))
        if "/cdn-cgi/l/email-protection#" in href:
            encoded = href.rsplit("#", 1)[-1]
            decoded = _decode_cf_email(encoded)
            if decoded:
                emails.append(decoded)

    text = soup.get_text(" ", strip=True)
    emails.extend(extract_emails(text))
    emails.extend(extract_emails(_deobfuscate_email_text(text)))
    return _clean_emails(emails)


def _discover_contact_links(html: str, page_url: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    discovered: list[str] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "").strip()
        label = link.get_text(" ", strip=True)
        haystack = f"{href} {label}".lower()
        if not any(hint in haystack for hint in CONTACT_LINK_HINTS):
            continue
        absolute = normalize_website_url(urljoin(page_url, href))
        if not absolute or not _same_site(absolute, base_url):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        discovered.append(absolute)

    return discovered


async def _fetch_html(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_seconds: float,
) -> str | None:
    try:
        response = await client.get(url, timeout=timeout_seconds)
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("content-type", "").lower()
        if content_type and "html" not in content_type and "text/plain" not in content_type:
            return None
        return response.text
    except Exception as exc:
        logger.debug("Website email fetch failed for %s: %s", url, exc)
        return None


async def extract_emails_from_website(
    website: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_pages: int = 4,
    timeout_seconds: float = 8.0,
) -> list[str]:
    base_url = normalize_website_url(website)
    if not base_url:
        return []

    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates = deque([base_url])
    for path in DEFAULT_CONTACT_PATHS:
        candidates.append(f"{origin}{path}")

    close_client = client is None
    active_client = client or httpx.AsyncClient(
        follow_redirects=True,
        headers={
            "User-Agent": pick_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    emails: list[str] = []
    visited: set[str] = set()
    try:
        while candidates and len(visited) < max(1, max_pages):
            url = candidates.popleft()
            if url in visited:
                continue
            visited.add(url)

            html = await _fetch_html(active_client, url, timeout_seconds=timeout_seconds)
            if not html:
                continue

            emails.extend(extract_emails_from_html(html))
            if emails:
                break

            for discovered_url in _discover_contact_links(html, url, base_url):
                if discovered_url not in visited:
                    candidates.append(discovered_url)
    finally:
        if close_client:
            await active_client.aclose()

    return _clean_emails(emails)


async def enrich_b2b_leads_with_website_emails(
    leads: list[ScrapedLead],
    *,
    max_pages_per_site: int = 4,
    timeout_seconds: float = 8.0,
    concurrency: int = 4,
) -> dict[str, int]:
    candidates = [lead for lead in leads if lead.website and not lead.emails]
    if not candidates:
        return {"checked": 0, "enriched": 0, "emails_found": 0}

    semaphore = asyncio.Semaphore(max(1, concurrency))
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0))
    limits = httpx.Limits(max_connections=max(1, concurrency), max_keepalive_connections=max(1, concurrency))
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        limits=limits,
        headers={
            "User-Agent": pick_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    ) as client:

        async def enrich_one(lead: ScrapedLead) -> int:
            async with semaphore:
                found = await extract_emails_from_website(
                    lead.website,
                    client=client,
                    max_pages=max_pages_per_site,
                    timeout_seconds=timeout_seconds,
                )
                lead.emails = _clean_emails((lead.emails or []) + found)
                return len(found)

        results = await asyncio.gather(*(enrich_one(lead) for lead in candidates))

    enriched = sum(1 for count in results if count > 0)
    return {
        "checked": len(candidates),
        "enriched": enriched,
        "emails_found": sum(results),
    }
