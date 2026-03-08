from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from winxtract.core.models import RawRecord
from winxtract.parsers.normalize import normalize_text
from winxtract.scrapers.base import BaseScraper, ScrapeContext
from winxtract.scrapers.open_data_json import dig_value
from winxtract.scrapers.registry import register_scraper


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [chunk.strip() for chunk in value.split(",") if chunk.strip()]
    return []


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


def _read_text_lines(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


@register_scraper
class RechercheEntreprisesApiScraper(BaseScraper):
    slug = "recherche_entreprises_api"

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        timeout_sec = float(ctx.source.params.get("timeout_seconds", 45))
        per_page = max(1, int(ctx.source.params.get("per_page", 25)))
        max_pages = max(1, int(ctx.source.params.get("max_pages_per_query", 2)))
        page_start = max(1, int(ctx.source.params.get("page_start", 1)))
        max_queries = max(1, int(ctx.source.params.get("max_queries", 200)))
        endpoint = str(ctx.source.params.get("api_url") or str(ctx.source.start_urls[0]))

        terms = _to_list(ctx.source.params.get("search_terms"))
        terms.extend(_read_text_lines(str(ctx.source.params.get("search_terms_file") or "").strip() or None))
        terms = _unique_keep_order(terms) or ["boulangerie"]

        cities = _to_list(ctx.source.params.get("cities"))
        cities.extend(_read_text_lines(str(ctx.source.params.get("cities_file") or "").strip() or None))
        cities = _unique_keep_order(cities)

        queries = self._queries(terms, cities)[:max_queries]

        async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
            for query in queries:
                for page in range(page_start, page_start + max_pages):
                    resp = await client.get(endpoint, params={"q": query, "page": page, "per_page": per_page})
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get("results", [])
                    if not isinstance(items, list) or not items:
                        break

                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        payload = self._build_payload(item)
                        yield RawRecord(
                            source_slug=ctx.source.slug,
                            page_url=str(resp.url),
                            payload=payload,
                        )

                    total = data.get("total_results") if isinstance(data, dict) else None
                    if isinstance(total, int) and page * per_page >= total:
                        break
                    if len(items) < per_page:
                        break

    def _queries(self, terms: list[str], cities: list[str]) -> list[str]:
        if not cities:
            return terms
        out: list[str] = []
        for term in terms:
            for city in cities:
                query = f"{term} {city}".strip()
                if query:
                    out.append(query)
        return out

    def _build_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        fields = {
            "name": normalize_text(
                self._str(
                    dig_value(item, "nom_complet")
                    or dig_value(item, "nom_raison_sociale")
                    or dig_value(item, "siren")
                )
            ),
            "city": normalize_text(
                self._str(
                    dig_value(item, "siege.libelle_commune")
                    or dig_value(item, "matching_etablissements.0.libelle_commune")
                )
            ),
            "website": normalize_text(self._str(dig_value(item, "siege.site_internet"))),
            "phone": normalize_text(self._str(dig_value(item, "siege.telephone"))),
            "address": normalize_text(
                self._str(
                    dig_value(item, "siege.adresse")
                    or dig_value(item, "matching_etablissements.0.adresse")
                )
            ),
            "category": normalize_text(
                self._str(dig_value(item, "activite_principale") or dig_value(item, "siege.activite_principale"))
            ),
            "description": normalize_text(
                self._str(
                    dig_value(item, "nature_juridique")
                    or dig_value(item, "section_activite_principale")
                    or dig_value(item, "tranche_effectif_salarie")
                )
            ),
        }
        text_parts = [str(v) for v in fields.values() if v]
        fields["full_text"] = " ".join(text_parts)
        return fields

    def _str(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)
