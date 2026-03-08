from pathlib import Path

import yaml

from winxtract.core.models import SourceConfig


_PROFILE_FLAGS = {
    "b2c_conforme": {
        "privacy_drop_person_records": True,
        "privacy_drop_private_email_records": True,
        "privacy_redact_name": True,
        "privacy_redact_contact": True,
        "privacy_redact_address": True,
        "privacy_redact_page_url": True,
        "privacy_sanitize_description": True,
    },
    "b2c_etendu": {
        "privacy_drop_person_records": False,
        "privacy_drop_private_email_records": False,
        "privacy_redact_name": False,
        "privacy_redact_contact": True,
        "privacy_redact_address": False,
        "privacy_redact_page_url": False,
        "privacy_sanitize_description": True,
    },
}


def list_source_entries(sources_dir: str) -> list[dict]:
    entries: list[dict] = []
    for path in sorted(Path(sources_dir).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        params = raw.get("params")
        stable_pack = bool(params.get("stable_pack", False)) if isinstance(params, dict) else False
        privacy_mode = str(params.get("privacy_mode", "none")) if isinstance(params, dict) else "none"
        privacy_profile = str(params.get("privacy_profile", "")) if isinstance(params, dict) else ""
        entries.append(
            {
                "path": str(path),
                "slug": raw.get("slug", path.stem),
                "name": raw.get("name") or raw.get("slug", path.stem),
                "scraper": raw.get("scraper", "unknown"),
                "enabled": bool(raw.get("enabled", False)),
                "stable_pack": stable_pack,
                "privacy_mode": privacy_mode,
                "privacy_profile": privacy_profile,
            }
        )
    return entries


def set_source_enabled(sources_dir: str, source_slug: str, enabled: bool) -> bool:
    for path in sorted(Path(sources_dir).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if raw.get("slug") != source_slug:
            continue
        raw["enabled"] = bool(enabled)
        path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=False), encoding="utf-8")
        return True
    return False


def set_source_privacy_profile(sources_dir: str, source_slug: str, profile: str) -> int:
    normalized = profile.strip().lower()
    if normalized not in {"none", "b2c_conforme", "b2c_etendu"}:
        raise ValueError("profile must be one of: none, b2c_conforme, b2c_etendu")

    changed = 0
    apply_all = source_slug in {"*", "all", ""}
    for path in sorted(Path(sources_dir).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        slug = raw.get("slug")
        if not slug:
            continue
        if not apply_all and slug != source_slug:
            continue

        params = raw.get("params")
        if not isinstance(params, dict):
            params = {}

        if normalized == "none":
            params["privacy_mode"] = "none"
            params.pop("privacy_profile", None)
            for key in list(_PROFILE_FLAGS["b2c_conforme"].keys()):
                params.pop(key, None)
        else:
            params["privacy_mode"] = "particulier_conforme"
            params["privacy_profile"] = normalized
            for key, value in _PROFILE_FLAGS[normalized].items():
                params[key] = value

        raw["params"] = params
        path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=False), encoding="utf-8")
        changed += 1
    return changed


def load_sources(sources_dir: str, only_slug: str | None = None) -> list[SourceConfig]:
    source_configs: list[SourceConfig] = []
    for path in sorted(Path(sources_dir).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        source = SourceConfig(**raw)
        if not source.enabled:
            continue
        if only_slug and source.slug != only_slug:
            continue
        source_configs.append(source)
    return source_configs
