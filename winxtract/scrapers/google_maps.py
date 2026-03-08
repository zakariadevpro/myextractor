from collections.abc import AsyncIterator
from copy import deepcopy

from winxtract.core.models import RawRecord, SourceConfig
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.generic_css import GenericCssScraper
from winxtract.scrapers.registry import register_scraper


@register_scraper
class GoogleMapsPublicScraper(GenericCssScraper):
    slug = "google_maps_public"

    DEFAULT_SELECTORS = {
        "card": "div[role='article']",
        "name": "div.qBF1Pd",
        "phone": "button[data-item-id*='phone']",
        "website": "a[data-item-id='authority']",
    }

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        merged = deepcopy(ctx.source)
        merged.selectors = {**self.DEFAULT_SELECTORS, **ctx.source.selectors}
        child_ctx = ScrapeContext(source=SourceConfig(**merged.model_dump()), browser_pool=ctx.browser_pool, logger=ctx.logger)
        async for raw in super().scrape(child_ctx):
            yield raw
