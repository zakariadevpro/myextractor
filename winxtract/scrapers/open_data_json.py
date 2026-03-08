from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from winxtract.core.models import RawRecord
from winxtract.parsers.normalize import normalize_text
from winxtract.scrapers.base import BaseScraper, ScrapeContext
from winxtract.scrapers.registry import register_scraper


def dig_value(obj: Any, path: str | None) -> Any:
    if not path:
        return None
    cur: Any = obj
    for part in path.split("."):
        token = part.strip()
        if not token:
            return None
        if isinstance(cur, dict):
            cur = cur.get(token)
            continue
        if isinstance(cur, list) and token.isdigit():
            idx = int(token)
            if 0 <= idx < len(cur):
                cur = cur[idx]
                continue
        return None
    return cur


def extract_items(payload: Any, items_path: str | None) -> list[Any]:
    if items_path:
        extracted = dig_value(payload, items_path)
    else:
        extracted = payload
    if isinstance(extracted, list):
        return extracted
    if isinstance(extracted, dict):
        return [extracted]
    return []


def build_paged_url(
    base_url: str,
    *,
    limit_param: str,
    offset_param: str,
    page_size: int,
    offset: int,
) -> str:
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[limit_param] = str(page_size)
    query[offset_param] = str(offset)
    new_query = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


@register_scraper
class OpenDataJsonScraper(BaseScraper):
    slug = "open_data_json"

    async def scrape(self, ctx: ScrapeContext) -> AsyncIterator[RawRecord]:
        items_path = str(ctx.source.params.get("items_path", "")).strip() or None
        timeout_sec = float(ctx.source.params.get("timeout_seconds", 30))
        max_items = int(ctx.source.params.get("max_items_per_url", 1000))
        pagination_mode = str(ctx.source.params.get("pagination_mode", "none")).strip().lower()
        page_size = int(ctx.source.params.get("page_size", 100))
        max_pages = int(ctx.source.params.get("max_pages", 1))
        limit_param = str(ctx.source.params.get("limit_param", "limit")).strip() or "limit"
        offset_param = str(ctx.source.params.get("offset_param", "offset")).strip() or "offset"
        selectors = ctx.source.selectors

        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            for source_url in map(str, ctx.source.start_urls):
                emitted = 0
                if pagination_mode == "offset":
                    for page_idx in range(max_pages):
                        offset = page_idx * page_size
                        request_url = build_paged_url(
                            source_url,
                            limit_param=limit_param,
                            offset_param=offset_param,
                            page_size=page_size,
                            offset=offset,
                        )
                        resp = await client.get(request_url)
                        resp.raise_for_status()
                        data = resp.json()
                        items = extract_items(data, items_path)
                        if not items:
                            break
                        for item in items:
                            if emitted >= max_items:
                                break
                            if not isinstance(item, dict):
                                continue
                            payload = self._build_payload(item, selectors)
                            yield RawRecord(
                                source_slug=ctx.source.slug,
                                page_url=request_url,
                                payload=payload,
                            )
                            emitted += 1
                        if emitted >= max_items:
                            break
                        total_count = data.get("total_count") if isinstance(data, dict) else None
                        if isinstance(total_count, int) and offset + len(items) >= total_count:
                            break
                        if len(items) < page_size:
                            break
                else:
                    resp = await client.get(source_url)
                    resp.raise_for_status()
                    data = resp.json()
                    items = extract_items(data, items_path)[:max_items]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        payload = self._build_payload(item, selectors)
                        yield RawRecord(
                            source_slug=ctx.source.slug,
                            page_url=source_url,
                            payload=payload,
                        )

    def _build_payload(self, item: dict[str, Any], selectors: dict[str, str]) -> dict[str, Any]:
        fields = {
            "name": normalize_text(self._str(dig_value(item, selectors.get("name")))),
            "city": normalize_text(self._str(dig_value(item, selectors.get("city")))),
            "website": normalize_text(self._str(dig_value(item, selectors.get("website")))),
            "phone": normalize_text(self._str(dig_value(item, selectors.get("phone")))),
            "address": normalize_text(self._str(dig_value(item, selectors.get("address")))),
            "category": normalize_text(self._str(dig_value(item, selectors.get("category")))),
            "description": normalize_text(self._str(dig_value(item, selectors.get("description")))),
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
