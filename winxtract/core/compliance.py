from winxtract.core.source_loader import list_source_entries


def resolve_export_target_sources(
    sources_dir: str,
    *,
    source_slug: str | None = None,
    source_slugs: list[str] | None = None,
) -> list[dict]:
    entries = [row for row in list_source_entries(sources_dir) if row["enabled"]]
    if source_slugs:
        slug_set = {slug.strip() for slug in source_slugs if slug and slug.strip()}
        return [row for row in entries if row["slug"] in slug_set]
    if source_slug:
        normalized = source_slug.strip()
        if not normalized or normalized in {"*", "all"}:
            return entries
        return [row for row in entries if row["slug"] == normalized]
    return entries


def find_non_compliant_sources(
    sources_dir: str,
    *,
    required_privacy_mode: str,
    source_slug: str | None = None,
    source_slugs: list[str] | None = None,
) -> list[str]:
    required = required_privacy_mode.strip().lower()
    if not required:
        return []

    targets = resolve_export_target_sources(
        sources_dir,
        source_slug=source_slug,
        source_slugs=source_slugs,
    )
    out: list[str] = []
    for row in targets:
        mode = str(row.get("privacy_mode", "none")).strip().lower()
        if mode != required:
            out.append(row["slug"])
    return out
