from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScrapedLead:
    """Standard lead data structure returned by all scrapers."""
    company_name: str
    address: str = ""
    postal_code: str = ""
    city: str = ""
    department: str = ""
    region: str = ""
    website: str = ""
    sector: str = ""
    siren: str = ""
    naf_code: str = ""
    source_url: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    source_name: str = "unknown"

    @abstractmethod
    async def search(
        self,
        keywords: list[str],
        city: str | None = None,
        radius_km: int | None = None,
        max_results: int = 100,
    ) -> list[ScrapedLead]:
        """Execute a search and return scraped leads."""
        ...

    @abstractmethod
    async def close(self):
        """Clean up resources (browser, connections)."""
        ...
