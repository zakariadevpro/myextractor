from collections.abc import AsyncIterator
from urllib.parse import urljoin

from winxtract.core.models import RawRecord
from winxtract.scrapers.base import BaseScraper, ScrapeContext
from winxtract.scrapers.registry import register_scraper


@register_scraper
class GenericCssScraper(BaseScraper):
    slug = "generic_css"

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        selectors = ctx.source.selectors
        card_sel = selectors.get("card")
        name_sel = selectors.get("name")
        city_sel = selectors.get("city")
        website_sel = selectors.get("website")
        phone_sel = selectors.get("phone")
        next_sel = selectors.get("next_page")
        max_pages = int(ctx.source.params.get("max_pages", 10))
        pagination_mode = str(ctx.source.params.get("pagination_mode", "click")).lower()

        if not card_sel:
            raise ValueError("Missing required selector: card")

        for start_url in map(str, ctx.source.start_urls):
            current_url: str | None = start_url
            visited: set[str] = set()
            page_count = 0
            while current_url and page_count < max_pages:
                if pagination_mode in {"rel_next", "href"} and current_url in visited:
                    break
                visited.add(current_url)
                async with ctx.browser_pool.open_page(
                    current_url,
                    respect_robots=ctx.source.respect_robots,
                ) as page:
                    cards = await page.query_selector_all(self._sel(card_sel))
                    for card in cards:
                        raw = RawRecord(
                            source_slug=ctx.source.slug,
                            page_url=page.url,
                            payload={
                                "name": await self._text(card, name_sel),
                                "city": await self._text(card, city_sel),
                                "website": await self._text(card, website_sel),
                                "phone": await self._text(card, phone_sel),
                                "full_text": await card.inner_text(),
                            },
                        )
                        yield raw

                    current_url = await self._resolve_next_url(page, next_sel, pagination_mode)
                    page_count += 1

    async def _text(self, node, selector: str | None) -> str | None:
        if not selector:
            return None
        target = await node.query_selector(self._sel(selector))
        if not target:
            return None
        return (await target.inner_text()).strip() or None

    def _sel(self, selector: str) -> str:
        raw = (selector or "").strip()
        if raw.startswith("css:"):
            return raw[4:].strip()
        if raw.startswith("xpath:"):
            return f"xpath={raw[6:].strip()}"
        if raw.startswith("//") or raw.startswith(".//"):
            return f"xpath={raw}"
        return raw

    async def _resolve_next_url(self, page, next_sel: str | None, mode: str) -> str | None:
        if mode == "rel_next":
            href = await page.get_attribute("link[rel='next']", "href")
            if href:
                return urljoin(page.url, href)
            return None
        if not next_sel:
            return None
        next_button = await page.query_selector(self._sel(next_sel))
        if not next_button:
            return None
        href = await next_button.get_attribute("href")
        if href:
            return urljoin(page.url, href)
        await next_button.click()
        await page.wait_for_load_state("domcontentloaded")
        return page.url
