from pathlib import Path

import yaml

from winxtract.core.compliance import find_non_compliant_sources


def _write_source(path: Path, slug: str, privacy_mode: str):
    payload = {
        "slug": slug,
        "name": slug,
        "scraper": "open_data_json",
        "enabled": True,
        "respect_robots": True,
        "start_urls": ["https://example.com/data.json"],
        "selectors": {"name": "name"},
        "params": {"privacy_mode": privacy_mode},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_find_non_compliant_sources(tmp_path):
    _write_source(tmp_path / "a.yaml", "a", "particulier_conforme")
    _write_source(tmp_path / "b.yaml", "b", "none")
    invalid = find_non_compliant_sources(
        str(tmp_path),
        required_privacy_mode="particulier_conforme",
    )
    assert invalid == ["b"]
