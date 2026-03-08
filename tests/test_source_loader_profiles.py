from pathlib import Path

import yaml

from winxtract.core.source_loader import list_source_entries, set_source_privacy_profile


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


def test_set_source_privacy_profile_all(tmp_path: Path):
    src1 = tmp_path / "s1.yaml"
    src2 = tmp_path / "s2.yaml"
    _write_source(src1, "s1")
    _write_source(src2, "s2")

    updated = set_source_privacy_profile(str(tmp_path), "*", "b2c_etendu")
    assert updated == 2

    raw1 = yaml.safe_load(src1.read_text(encoding="utf-8"))
    raw2 = yaml.safe_load(src2.read_text(encoding="utf-8"))
    for raw in (raw1, raw2):
        assert raw["params"]["privacy_mode"] == "particulier_conforme"
        assert raw["params"]["privacy_profile"] == "b2c_etendu"
        assert raw["params"]["privacy_drop_person_records"] is False


def test_set_source_privacy_profile_none(tmp_path: Path):
    src = tmp_path / "s1.yaml"
    _write_source(src, "s1")
    set_source_privacy_profile(str(tmp_path), "s1", "b2c_conforme")
    updated = set_source_privacy_profile(str(tmp_path), "s1", "none")
    assert updated == 1
    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    assert raw["params"]["privacy_mode"] == "none"
    assert "privacy_profile" not in raw["params"]


def test_list_source_entries_exposes_stable_pack(tmp_path: Path):
    src = tmp_path / "s1.yaml"
    _write_source(src, "s1")
    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    raw["params"]["stable_pack"] = True
    raw["params"]["privacy_mode"] = "particulier_conforme"
    raw["params"]["privacy_profile"] = "b2c_conforme"
    src.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    rows = list_source_entries(str(tmp_path))
    assert len(rows) == 1
    assert rows[0]["stable_pack"] is True
    assert rows[0]["privacy_mode"] == "particulier_conforme"
    assert rows[0]["privacy_profile"] == "b2c_conforme"
