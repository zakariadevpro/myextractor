from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from winxtract.storage.db import ScrapeJobORM, create_engine_from_url, init_db
from winxtract.storage.source_health import compute_source_health


def _write_source(path: Path, slug: str) -> None:
    payload = {
        "slug": slug,
        "name": slug,
        "scraper": "open_data_json",
        "enabled": True,
        "respect_robots": True,
        "start_urls": ["https://example.com/data.json"],
        "selectors": {"name": "name"},
        "params": {},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_compute_source_health_with_auto_disable(tmp_path):
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    _write_source(sources_dir / "s1.yaml", "s1")
    _write_source(sources_dir / "s2.yaml", "s2")

    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'health.db'}")
    init_db(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add_all(
            [
                ScrapeJobORM(source_slug="s1", status="failed", errors=2, leads_extracted=0, finished_at=now),
                ScrapeJobORM(source_slug="s1", status="failed", errors=1, leads_extracted=0, finished_at=now),
                ScrapeJobORM(source_slug="s1", status="failed", errors=3, leads_extracted=0, finished_at=now),
                ScrapeJobORM(source_slug="s2", status="success", errors=0, leads_extracted=10, finished_at=now),
                ScrapeJobORM(source_slug="s2", status="failed", errors=1, leads_extracted=2, finished_at=now),
            ]
        )
        session.commit()

        report = compute_source_health(
            session,
            sources_dir=str(sources_dir),
            window_jobs=5,
            auto_disable_failures=3,
            apply_changes=True,
        )

    assert report["sources_count"] == 2
    assert report["disabled_now"] == 1
    by_slug = {row["source_slug"]: row for row in report["items"]}
    assert by_slug["s1"]["consecutive_failures"] == 3
    assert by_slug["s1"]["disabled_now"] is True
    assert by_slug["s2"]["consecutive_failures"] == 1

    raw_s1 = yaml.safe_load((sources_dir / "s1.yaml").read_text(encoding="utf-8"))
    raw_s2 = yaml.safe_load((sources_dir / "s2.yaml").read_text(encoding="utf-8"))
    assert raw_s1["enabled"] is False
    assert raw_s2["enabled"] is True
