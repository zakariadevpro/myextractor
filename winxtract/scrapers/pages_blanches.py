from collections.abc import AsyncIterator
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from winxtract.core.models import RawRecord, SourceConfig
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.generic_css import GenericCssScraper
from winxtract.scrapers.registry import register_scraper


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [chunk.strip() for chunk in value.split(",") if chunk.strip()]
    return []


def _read_text_lines(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _unique_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _build_seed_urls(params: dict[str, Any]) -> list[str]:
    template = (
        str(params.get("query_url_template") or "").strip()
        or "https://www.pagesjaunes.fr/pagesblanches/recherche?quoiqui={name}&ou={city}"
    )
    seed_names = _to_list(params.get("seed_names"))
    seed_names.extend(_read_text_lines(str(params.get("seed_names_file") or "").strip() or None))
    seed_names = _unique_keep_order(seed_names)

    cities = _to_list(params.get("cities"))
    cities.extend(_read_text_lines(str(params.get("cities_file") or "").strip() or None))
    cities = _unique_keep_order(cities)

    if not seed_names or not cities:
        return []

    max_queries = max(1, int(params.get("max_queries", 120)))
    urls: list[str] = []
    for name in seed_names:
        for city in cities:
            if len(urls) >= max_queries:
                return urls
            urls.append(template.format(name=quote_plus(name), city=quote_plus(city)))
    return urls


@register_scraper
class PagesBlanchesPublicScraper(GenericCssScraper):
    slug = "pages_blanches_public"

    DEFAULT_SELECTORS = {
        "card": "li.bi-bloc, li.bi-pro, article.bi-bloc",
        "name": "h2 a, h3 a, .denomination-links a",
        "city": ".adresse, .bi-address",
        "phone": "strong.num, .number-contact, [data-phone]",
        "website": "a.btn-site, a[href^='http']",
        "next_page": "a.pagination-next, a[rel='next']",
    }

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        merged = deepcopy(ctx.source)
        merged.selectors = {**self.DEFAULT_SELECTORS, **ctx.source.selectors}
        generated_urls = _build_seed_urls(ctx.source.params)
        if generated_urls:
            # Keep deterministic order while avoiding duplicates across static and generated seeds.
            merged.start_urls = list(dict.fromkeys([*merged.start_urls, *generated_urls]))
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
                    "PagesBlanches appears protected by anti-bot checks from this environment."
                )
        child_ctx = ScrapeContext(source=local_source, browser_pool=ctx.browser_pool, logger=ctx.logger)
        async for raw in super().scrape(child_ctx):
            yield raw
