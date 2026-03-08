import csv
import io
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx

from winxtract.core.models import RawRecord
from winxtract.parsers.normalize import normalize_text
from winxtract.scrapers.base import BaseScraper, ScrapeContext
from winxtract.scrapers.open_data_json import dig_value, extract_items
from winxtract.scrapers.registry import register_scraper

_FIELD_FALLBACKS: dict[str, list[str]] = {
    "name": ["name", "nom", "enseigne", "identifiantPM", "id", "title"],
    "city": ["city", "ville", "commune", "Commune", "libelle_commune", "nom_commune"],
    "website": ["website", "site", "url", "lien", "web"],
    "phone": ["phone", "telephone", "tel", "numero", "contact_phone"],
    "address": ["address", "adresse", "geo_adresse", "voie", "libelle_voie"],
    "category": ["category", "categorie", "type", "activite", "activite_principale"],
    "description": ["description", "desc", "notes", "commentaire"],
}


def resolve_dataset_api_url(start_url: str) -> str | None:
    parsed = urlparse(start_url)
    host = parsed.netloc.lower()
    if "data.gouv.fr" not in host:
        return None

    segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
    if len(segments) >= 4 and segments[0] == "api" and segments[1] == "1" and segments[2] == "datasets":
        slug = segments[3]
        return f"https://www.data.gouv.fr/api/1/datasets/{slug}/"

    if "datasets" in segments:
        idx = segments.index("datasets")
        if idx + 1 < len(segments):
            slug = segments[idx + 1]
            return f"https://www.data.gouv.fr/api/1/datasets/{slug}/"
    return None


def pick_best_resource(
    resources: list[dict[str, Any]],
    *,
    preferred_formats: list[str],
    title_contains: str | None,
) -> dict[str, Any] | None:
    if not resources:
        return None

    normalized_formats = [fmt.strip().lower() for fmt in preferred_formats if fmt and fmt.strip()]
    title_filter = (title_contains or "").strip().lower()
    best: tuple[int, dict[str, Any]] | None = None

    for resource in resources:
        url = str(resource.get("url") or "").strip()
        if not url:
            continue
        score = 0
        fmt = str(resource.get("format") or "").strip().lower()
        rtype = str(resource.get("type") or "").strip().lower()
        rtitle = str(resource.get("title") or "").strip().lower()

        if title_filter:
            if title_filter in rtitle:
                score += 40
            else:
                continue
        if fmt in normalized_formats:
            score += 100 - normalized_formats.index(fmt)
        if rtype == "main":
            score += 20
        if rtype == "api":
            score += 10

        ranked = (score, resource)
        if best is None or ranked[0] > best[0]:
            best = ranked

    return best[1] if best else resources[0]


def _parse_preferred_formats(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip().lower() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()]
    return ["csv", "json", "geojson"]


def _csv_delimiter(text: str, configured: str | None) -> str:
    if configured:
        return configured
    sample = "\n".join(text.splitlines()[:10])
    if not sample:
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        return dialect.delimiter
    except Exception:
        semicolons = sample.count(";")
        commas = sample.count(",")
        return ";" if semicolons > commas else ","


def _iter_csv_rows(text: str, *, delimiter: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader]


@register_scraper
class DataGouvDatasetScraper(BaseScraper):
    slug = "data_gouv_dataset"

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        timeout_sec = float(ctx.source.params.get("timeout_seconds", 30))
        max_items = int(ctx.source.params.get("max_items_per_resource", 5000))
        items_path = str(ctx.source.params.get("items_path", "")).strip() or None
        preferred_formats = _parse_preferred_formats(ctx.source.params.get("preferred_formats"))
        title_contains = str(ctx.source.params.get("resource_title_contains", "")).strip() or None
        csv_delimiter = str(ctx.source.params.get("csv_delimiter", "")).strip() or None
        selectors = ctx.source.selectors

        async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
            for start_url in map(str, ctx.source.start_urls):
                dataset_api = resolve_dataset_api_url(start_url)
                source_page_url = start_url
                resource_url = start_url
                format_hint: str | None = None

                if dataset_api:
                    dataset_resp = await client.get(dataset_api)
                    dataset_resp.raise_for_status()
                    dataset_obj = dataset_resp.json()
                    source_page_url = str(dataset_obj.get("page") or start_url)
                    resources = dataset_obj.get("resources", [])
                    selected = pick_best_resource(
                        resources,
                        preferred_formats=preferred_formats,
                        title_contains=title_contains,
                    )
                    if not selected:
                        continue
                    resource_url = str(selected.get("url") or "").strip()
                    format_hint = str(selected.get("format") or "").strip().lower() or None
                    if not resource_url:
                        continue

                resource_resp = await client.get(resource_url)
                resource_resp.raise_for_status()
                content_type = (resource_resp.headers.get("content-type") or "").lower()
                parsed_count = 0

                if self._is_json_like(content_type, format_hint, resource_url):
                    payload = resource_resp.json()
                    rows = self._json_rows(payload, items_path)
                else:
                    text = resource_resp.text
                    delimiter = _csv_delimiter(text, csv_delimiter)
                    rows = _iter_csv_rows(text, delimiter=delimiter)

                for row in rows:
                    if parsed_count >= max_items:
                        break
                    if not isinstance(row, dict):
                        continue
                    payload = self._build_payload(row, selectors)
                    yield RawRecord(
                        source_slug=ctx.source.slug,
                        page_url=source_page_url,
                        payload=payload,
                    )
                    parsed_count += 1

    def _is_json_like(self, content_type: str, format_hint: str | None, url: str) -> bool:
        if "json" in content_type:
            return True
        if format_hint in {"json", "geojson"}:
            return True
        return url.lower().endswith(".json") or url.lower().endswith(".geojson")

    def _json_rows(self, payload: Any, items_path: str | None) -> list[Any]:
        if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
            features = payload.get("features")
            if isinstance(features, list):
                return features
        if not items_path and isinstance(payload, dict) and isinstance(payload.get("results"), list):
            return payload["results"]
        return extract_items(payload, items_path)

    def _build_payload(self, item: dict[str, Any], selectors: dict[str, str]) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for field_name in _FIELD_FALLBACKS.keys():
            selector = selectors.get(field_name)
            value = None
            if selector:
                value = dig_value(item, selector)
            if value is None:
                for candidate in _FIELD_FALLBACKS[field_name]:
                    value = dig_value(item, candidate)
                    if value is not None and value != "":
                        break
            fields[field_name] = normalize_text(self._str(value))

        text_parts = [str(v) for v in fields.values() if v]
        fields["full_text"] = " ".join(text_parts)
        return fields

    def _str(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)
