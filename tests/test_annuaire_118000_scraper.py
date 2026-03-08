import re
from collections import deque

from winxtract.scrapers.annuaire_118000 import Annuaire118000PublicScraper


def test_enqueue_url_discovery_filters_host_and_pattern():
    scraper = Annuaire118000PublicScraper()
    pending: deque[str] = deque()
    queued: set[str] = set()
    seen: set[str] = set()
    patterns = [re.compile(r"^https://annuaire\.118000\.fr/v_[^?#]+")]
    allowed_hosts = {"annuaire.118000.fr"}

    assert scraper._enqueue_url(
        "/v_paris_75",
        base_url="https://annuaire.118000.fr/",
        pending=pending,
        queued=queued,
        seen=seen,
        allowed_hosts=allowed_hosts,
        discovery_patterns=patterns,
        require_discovery_pattern=True,
    )
    assert list(pending) == ["https://annuaire.118000.fr/v_paris_75"]

    assert not scraper._enqueue_url(
        "https://example.org/v_paris_75",
        base_url="https://annuaire.118000.fr/",
        pending=pending,
        queued=queued,
        seen=seen,
        allowed_hosts=allowed_hosts,
        discovery_patterns=patterns,
        require_discovery_pattern=True,
    )

    assert not scraper._enqueue_url(
        "/contact",
        base_url="https://annuaire.118000.fr/",
        pending=pending,
        queued=queued,
        seen=seen,
        allowed_hosts=allowed_hosts,
        discovery_patterns=patterns,
        require_discovery_pattern=True,
    )


def test_normalize_url_removes_fragment_and_trailing_slash():
    scraper = Annuaire118000PublicScraper()
    normalized = scraper._normalize_url("https://annuaire.118000.fr/v_paris_75/#top")
    assert normalized == "https://annuaire.118000.fr/v_paris_75"
