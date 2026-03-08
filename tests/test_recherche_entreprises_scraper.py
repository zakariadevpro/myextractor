from urllib.parse import parse_qs, urlparse

import pytest

from winxtract.core.models import SourceConfig
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.recherche_entreprises_api import RechercheEntreprisesApiScraper


@pytest.mark.asyncio
async def test_recherche_entreprises_scraper_paginated(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        def __init__(self, payload: dict):
            self._payload = payload
            self.url = "https://recherche-entreprises.api.gouv.fr/search?q=test&page=1&per_page=2"

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

        async def get(self, url: str, params: dict):
            q = params["q"]
            page = int(params["page"])
            _ = parse_qs(urlparse(f"{url}?q={q}&page={page}").query)
            if page == 1:
                return FakeResponse(
                    {
                        "total_results": 3,
                        "results": [
                            {
                                "nom_complet": "Boulangerie A",
                                "siege": {"libelle_commune": "PARIS", "adresse": "1 rue A"},
                                "activite_principale": "47.24Z",
                            },
                            {
                                "nom_complet": "Boulangerie B",
                                "siege": {"libelle_commune": "PARIS", "adresse": "2 rue B"},
                                "activite_principale": "47.24Z",
                            },
                        ],
                    }
                )
            if page == 2:
                return FakeResponse(
                    {
                        "total_results": 3,
                        "results": [
                            {
                                "nom_complet": "Boulangerie C",
                                "siege": {"libelle_commune": "PARIS", "adresse": "3 rue C"},
                                "activite_principale": "47.24Z",
                            }
                        ],
                    }
                )
            return FakeResponse({"total_results": 3, "results": []})

    monkeypatch.setattr("winxtract.scrapers.recherche_entreprises_api.httpx.AsyncClient", FakeAsyncClient)

    source = SourceConfig(
        slug="re",
        name="recherche-entreprises.api.gouv.fr",
        scraper="recherche_entreprises_api",
        start_urls=["https://recherche-entreprises.api.gouv.fr/search"],
        selectors={},
        params={
            "search_terms": ["boulangerie"],
            "cities": ["Paris"],
            "per_page": 2,
            "max_pages_per_query": 3,
        },
    )
    ctx = ScrapeContext(source=source, browser_pool=None, logger=None)  # type: ignore[arg-type]
    scraper = RechercheEntreprisesApiScraper()
    rows = [row async for row in scraper.scrape(ctx)]

    assert len(rows) == 3
    assert [row.payload["name"] for row in rows] == ["Boulangerie A", "Boulangerie B", "Boulangerie C"]


@pytest.mark.asyncio
async def test_recherche_entreprises_scraper_reads_cities_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    captured_queries: list[str] = []

    class FakeResponse:
        def __init__(self, query: str):
            self._query = query
            self.url = f"https://recherche-entreprises.api.gouv.fr/search?q={query}&page=1&per_page=1"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "total_results": 1,
                "results": [
                    {
                        "nom_complet": f"Entreprise {self._query}",
                        "siege": {"libelle_commune": "PARIS", "adresse": "1 rue test"},
                        "activite_principale": "47.24Z",
                    }
                ],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params: dict):
            captured_queries.append(str(params["q"]))
            return FakeResponse(str(params["q"]))

    monkeypatch.setattr("winxtract.scrapers.recherche_entreprises_api.httpx.AsyncClient", FakeAsyncClient)

    cities_file = tmp_path / "cities.txt"
    cities_file.write_text("Paris\nLyon\n", encoding="utf-8")

    source = SourceConfig(
        slug="re_file",
        name="recherche-entreprises.api.gouv.fr",
        scraper="recherche_entreprises_api",
        start_urls=["https://recherche-entreprises.api.gouv.fr/search"],
        selectors={},
        params={
            "search_terms": ["plombier"],
            "cities_file": str(cities_file),
            "max_queries": 2,
            "per_page": 1,
            "max_pages_per_query": 1,
        },
    )
    ctx = ScrapeContext(source=source, browser_pool=None, logger=None)  # type: ignore[arg-type]
    scraper = RechercheEntreprisesApiScraper()
    rows = [row async for row in scraper.scrape(ctx)]

    assert len(rows) == 2
    assert captured_queries == ["plombier Paris", "plombier Lyon"]
