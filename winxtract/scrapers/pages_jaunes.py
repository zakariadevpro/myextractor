from collections.abc import AsyncIterator
from copy import deepcopy

from winxtract.core.models import RawRecord, SourceConfig
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.generic_css import GenericCssScraper
from winxtract.scrapers.registry import register_scraper


@register_scraper
class PagesJaunesPublicScraper(GenericCssScraper):
    slug = "pages_jaunes_public"

    DEFAULT_SELECTORS = {
        "card": "li.bi-bloc",
        "name": "h2 a",
        "city": "a.adresse",
        "phone": "strong.num",
        "website": "a.btn-site",
        "next_page": "a.pagination-next",
    }

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        merged = deepcopy(ctx.source)
        merged.selectors = {**self.DEFAULT_SELECTORS, **ctx.source.selectors}
        local_source = SourceConfig(**merged.model_dump())
        async with ctx.browser_pool.open_page(
            str(local_source.start_urls[0]),
            respect_robots=local_source.respect_robots,
        ) as probe:
            challenge_text = (await probe.content()).lower()
            blocked_patterns = [
                "noindex,nofollow",
                "access denied",
                "captcha",
                "just a moment",
                "un instant",
                "trafic anormal",
                "acces refuse",
                "bloqu",
            ]
            if any(pattern in challenge_text for pattern in blocked_patterns):
                raise PermissionError(
                    "PagesJaunes appears protected by anti-bot checks from this environment."
                )
        child_ctx = ScrapeContext(source=local_source, browser_pool=ctx.browser_pool, logger=ctx.logger)
        async for raw in super().scrape(child_ctx):
            yield raw
