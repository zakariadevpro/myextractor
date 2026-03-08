import re
from collections import deque
from collections.abc import AsyncIterator
from urllib.parse import urljoin, urlparse, urlunparse

from winxtract.core.models import RawRecord
from winxtract.parsers.normalize import normalize_text
from winxtract.scrapers.base import BaseScraper, ScrapeContext
from winxtract.scrapers.registry import register_scraper


@register_scraper
class Annuaire118000PublicScraper(BaseScraper):
    slug = "annuaire_118000_public"

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        max_pages = int(ctx.source.params.get("max_pages", 5))
        card_selector = ctx.source.selectors.get("card", "section.card.part.lnk")
        name_selector = ctx.source.selectors.get("name", "h2.name a")
        address_selector = ctx.source.selectors.get("address", ".address")
        phone_selector = ctx.source.selectors.get("phone", ".phone")
        next_selector = ctx.source.selectors.get("next_page", "link[rel='next']")
        allow_link_discovery = bool(ctx.source.params.get("allow_link_discovery", False))
        max_discovered_urls = int(ctx.source.params.get("max_discovered_urls", 300))
        max_links_per_page = int(ctx.source.params.get("max_links_per_page", 200))
        allowed_hosts = {
            str(host).strip().lower()
            for host in ctx.source.params.get("allowed_hosts", ["annuaire.118000.fr"])
            if str(host).strip()
        }
        if not allowed_hosts:
            allowed_hosts = {"annuaire.118000.fr"}
        raw_patterns = ctx.source.params.get("discovery_patterns", [r"^https://annuaire\.118000\.fr/v_[^?#]+"])
        if isinstance(raw_patterns, str):
            raw_patterns = [raw_patterns]
        discovery_patterns = [re.compile(str(pattern)) for pattern in raw_patterns if str(pattern).strip()]

        pending_urls: deque[str] = deque()
        queued_urls: set[str] = set()
        seen_urls: set[str] = set()
        for seed in map(str, ctx.source.start_urls):
            normalized = self._normalize_url(seed)
            if normalized and normalized not in queued_urls:
                pending_urls.append(normalized)
                queued_urls.add(normalized)

        discovered_count = 0
        page_count = 0
        while pending_urls and page_count < max_pages:
            current_url = pending_urls.popleft()
            if current_url in seen_urls:
                continue
            seen_urls.add(current_url)
            async with ctx.browser_pool.open_page(
                current_url,
                respect_robots=ctx.source.respect_robots,
            ) as page:
                cards = await page.query_selector_all(card_selector)
                for card in cards:
                    name = await self._text(card, name_selector)
                    address = await self._text(card, address_selector)
                    phone = await self._text(card, phone_selector)
                    detail_url = await card.get_attribute("data-url")
                    city = self._extract_city(address)
                    raw = RawRecord(
                        source_slug=ctx.source.slug,
                        page_url=page.url,
                        payload={
                            "name": normalize_text(name),
                            "city": normalize_text(city),
                            "address": normalize_text(address),
                            "phone": normalize_text(phone),
                            "website": None,
                            "detail_url": detail_url,
                            "full_text": normalize_text(await card.inner_text()) or "",
                        },
                    )
                    yield raw

                next_href = await page.get_attribute(next_selector, "href")
                self._enqueue_url(
                    next_href,
                    base_url=page.url,
                    pending=pending_urls,
                    queued=queued_urls,
                    seen=seen_urls,
                    allowed_hosts=allowed_hosts,
                    discovery_patterns=discovery_patterns,
                    require_discovery_pattern=False,
                )

                if allow_link_discovery and discovered_count < max_discovered_urls:
                    hrefs = await page.eval_on_selector_all(
                        "a[href]",
                        "els => els.map(el => el.getAttribute('href')).filter(Boolean)",
                    )
                    for href in list(hrefs)[:max_links_per_page]:
                        if discovered_count >= max_discovered_urls:
                            break
                        if self._enqueue_url(
                            href,
                            base_url=page.url,
                            pending=pending_urls,
                            queued=queued_urls,
                            seen=seen_urls,
                            allowed_hosts=allowed_hosts,
                            discovery_patterns=discovery_patterns,
                            require_discovery_pattern=True,
                        ):
                            discovered_count += 1
            page_count += 1

    async def _text(self, node, selector: str) -> str | None:
        element = await node.query_selector(selector)
        if not element:
            return None
        value = await element.inner_text()
        return value.strip() or None

    def _extract_city(self, address: str | None) -> str | None:
        if not address:
            return None
        lines = [part.strip() for part in address.splitlines() if part.strip()]
        if not lines:
            return None
        last = lines[-1]
        # Example: "75017 Paris" -> "Paris"
        parts = last.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            return parts[1]
        return last

    def _enqueue_url(
        self,
        href: str | None,
        *,
        base_url: str,
        pending: deque[str],
        queued: set[str],
        seen: set[str],
        allowed_hosts: set[str],
        discovery_patterns: list[re.Pattern[str]],
        require_discovery_pattern: bool,
    ) -> bool:
        if not href:
            return False
        absolute = self._normalize_url(urljoin(base_url, href))
        if not absolute:
            return False
        if absolute in queued or absolute in seen:
            return False
        if not self._is_allowed_host(absolute, allowed_hosts):
            return False
        if require_discovery_pattern and discovery_patterns:
            if not any(pattern.search(absolute) for pattern in discovery_patterns):
                return False
        queued.add(absolute)
        pending.append(absolute)
        return True

    def _normalize_url(self, value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            return None
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))

    def _is_allowed_host(self, value: str, allowed_hosts: set[str]) -> bool:
        host = (urlparse(value).hostname or "").lower()
        if not host:
            return False
        for allowed in allowed_hosts:
            allowed_host = allowed.lower().lstrip(".")
            if host == allowed_host or host.endswith(f".{allowed_host}"):
                return True
        return False
