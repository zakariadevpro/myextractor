import pytest

from winxtract.core.models import SourceConfig
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.data_gouv_dataset import DataGouvDatasetScraper, resolve_dataset_api_url


def test_resolve_dataset_api_url_from_public_page():
    url = "https://www.data.gouv.fr/fr/datasets/mon-dataset-test/"
    assert resolve_dataset_api_url(url) == "https://www.data.gouv.fr/api/1/datasets/mon-dataset-test/"


@pytest.mark.asyncio
async def test_data_gouv_dataset_scraper_from_dataset_metadata(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        def __init__(self, *, payload=None, text=None, headers=None):
            self._payload = payload
            self._text = text
            self.headers = headers or {}

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

        @property
        def text(self):
            return self._text or ""

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str):
            if "api/1/datasets/mon-dataset-test" in url:
                return FakeResponse(
                    payload={
                        "page": "https://www.data.gouv.fr/fr/datasets/mon-dataset-test/",
                        "resources": [
                            {
                                "title": "annexe1.csv",
                                "format": "csv",
                                "type": "main",
                                "url": "https://static.data.gouv.fr/resources/annexe1.csv",
                            }
                        ],
                    },
                    headers={"content-type": "application/json"},
                )
            if "static.data.gouv.fr/resources/annexe1.csv" in url:
                return FakeResponse(
                    text="identifiantPM;Commune\nFI-0001;PARIS\nFI-0002;LYON\n",
                    headers={"content-type": "text/csv"},
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("winxtract.scrapers.data_gouv_dataset.httpx.AsyncClient", FakeAsyncClient)

    source = SourceConfig(
        slug="arcep_pm",
        name="data.gouv.fr/arcep-points-mutualisation",
        scraper="data_gouv_dataset",
        start_urls=["https://www.data.gouv.fr/fr/datasets/mon-dataset-test/"],
        selectors={"name": "identifiantPM", "city": "Commune"},
        params={"preferred_formats": ["csv"], "resource_title_contains": "annexe1"},
    )
    ctx = ScrapeContext(source=source, browser_pool=None, logger=None)  # type: ignore[arg-type]
    scraper = DataGouvDatasetScraper()

    rows = [row async for row in scraper.scrape(ctx)]
    assert len(rows) == 2
    assert rows[0].payload["name"] == "FI-0001"
    assert rows[0].payload["city"] == "PARIS"
