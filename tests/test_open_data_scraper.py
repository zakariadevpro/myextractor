from urllib.parse import parse_qs, urlparse

import pytest

from winxtract.core.models import SourceConfig
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.open_data_json import (
    OpenDataJsonScraper,
    build_paged_url,
    dig_value,
    extract_items,
)


def test_dig_value_dot_path():
    row = {"a": {"b": [{"name": "x"}, {"name": "y"}]}}
    assert dig_value(row, "a.b.1.name") == "y"
    assert dig_value(row, "a.b.2.name") is None
    assert dig_value(row, "a.z") is None


def test_extract_items_from_path():
    payload = {"results": [{"id": 1}, {"id": 2}]}
    items = extract_items(payload, "results")
    assert len(items) == 2
    assert items[0]["id"] == 1


def test_extract_items_when_payload_is_single_object():
    payload = {"id": 10, "name": "lead"}
    items = extract_items(payload, None)
    assert len(items) == 1
    assert items[0]["id"] == 10


def test_build_paged_url_merges_existing_query():
    url = build_paged_url(
        "https://example.com/data?dataset=shops",
        limit_param="limit",
        offset_param="offset",
        page_size=100,
        offset=200,
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs["dataset"] == ["shops"]
    assert qs["limit"] == ["100"]
    assert qs["offset"] == ["200"]


@pytest.mark.asyncio
async def test_open_data_scraper_offset_pagination(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str) -> FakeResponse:
            calls.append(url)
            qs = parse_qs(urlparse(url).query)
            offset = int(qs.get("offset", ["0"])[0])
            if offset == 0:
                return FakeResponse(
                    {
                        "total_count": 3,
                        "results": [{"enseigne": "A"}, {"enseigne": "B"}],
                    }
                )
            if offset == 2:
                return FakeResponse({"total_count": 3, "results": [{"enseigne": "C"}]})
            return FakeResponse({"total_count": 3, "results": []})

    monkeypatch.setattr("winxtract.scrapers.open_data_json.httpx.AsyncClient", FakeAsyncClient)

    source = SourceConfig(
        slug="od",
        scraper="open_data_json",
        start_urls=["https://example.com/data"],
        selectors={"name": "enseigne"},
        params={
            "items_path": "results",
            "pagination_mode": "offset",
            "page_size": 2,
            "max_pages": 5,
            "limit_param": "limit",
            "offset_param": "offset",
        },
    )
    ctx = ScrapeContext(source=source, browser_pool=None, logger=None)  # type: ignore[arg-type]
    scraper = OpenDataJsonScraper()
    rows = [row async for row in scraper.scrape(ctx)]

    assert len(rows) == 3
    assert [row.payload["name"] for row in rows] == ["A", "B", "C"]
    assert len(calls) == 2
    assert "offset=0" in calls[0]
    assert "offset=2" in calls[1]
