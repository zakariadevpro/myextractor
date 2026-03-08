from winxtract.scrapers.base import BaseScraper

_REGISTRY: dict[str, type[BaseScraper]] = {}


def register_scraper(scraper_cls: type[BaseScraper]) -> type[BaseScraper]:
    slug = getattr(scraper_cls, "slug", None)
    if not slug:
        raise ValueError("Scraper class must define `slug`")
    _REGISTRY[slug] = scraper_cls
    return scraper_cls


def get_scraper(slug: str) -> type[BaseScraper]:
    if slug not in _REGISTRY:
        raise KeyError(f"Unknown scraper plugin: {slug}")
    return _REGISTRY[slug]
