from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from winxtract.core.browser_pool import BrowserPool
from winxtract.core.models import RawRecord, SourceConfig


@dataclass(slots=True)
class ScrapeContext:
    source: SourceConfig
    browser_pool: BrowserPool
    logger: object


class BaseScraper(ABC):
    slug: str

    @abstractmethod
    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        raise NotImplementedError
