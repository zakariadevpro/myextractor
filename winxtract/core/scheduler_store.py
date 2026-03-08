from pathlib import Path

import yaml


DEFAULT_SCHEDULES = {
    "schedules": [
        {
            "source_slug": "annuaire.118000.fr",
            "enabled": False,
            "interval_minutes": 60,
            "export_format": "csv",
            "min_score": 0,
        }
    ]
}


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(DEFAULT_SCHEDULES, sort_keys=False), encoding="utf-8")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {"schedules": []}


def _save(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def list_schedules(path: str) -> list[dict]:
    data = _load(path)
    rows: list[dict] = []
    for entry in data.get("schedules", []):
        rows.append(
            {
                "source_slug": str(entry.get("source_slug", "")).strip(),
                "enabled": bool(entry.get("enabled", False)),
                "interval_minutes": int(entry.get("interval_minutes", 60)),
                "export_format": str(entry.get("export_format", "csv")),
                "min_score": int(entry.get("min_score", 0)),
            }
        )
    return rows


def upsert_schedule(
    path: str,
    *,
    source_slug: str,
    enabled: bool,
    interval_minutes: int,
    export_format: str,
    min_score: int,
) -> None:
    data = _load(path)
    schedules = data.get("schedules", [])
    found = False
    for entry in schedules:
        if str(entry.get("source_slug", "")).strip() != source_slug:
            continue
        entry["enabled"] = bool(enabled)
        entry["interval_minutes"] = max(1, int(interval_minutes))
        entry["export_format"] = export_format
        entry["min_score"] = max(0, min(100, int(min_score)))
        found = True
        break
    if not found:
        schedules.append(
            {
                "source_slug": source_slug,
                "enabled": bool(enabled),
                "interval_minutes": max(1, int(interval_minutes)),
                "export_format": export_format,
                "min_score": max(0, min(100, int(min_score))),
            }
        )
    data["schedules"] = schedules
    _save(path, data)


def set_schedule_enabled(path: str, source_slug: str, enabled: bool) -> bool:
    data = _load(path)
    schedules = data.get("schedules", [])
    for entry in schedules:
        if str(entry.get("source_slug", "")).strip() == source_slug:
            entry["enabled"] = bool(enabled)
            _save(path, data)
            return True
    return False
