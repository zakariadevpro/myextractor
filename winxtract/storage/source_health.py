from sqlalchemy import select
from sqlalchemy.orm import Session

from winxtract.core.source_loader import list_source_entries, set_source_enabled
from winxtract.storage.db import ScrapeJobORM


def _consecutive_failures(jobs: list[ScrapeJobORM]) -> int:
    count = 0
    for job in jobs:
        if job.status == "failed":
            count += 1
            continue
        break
    return count


def compute_source_health(
    session: Session,
    *,
    sources_dir: str,
    window_jobs: int = 10,
    auto_disable_failures: int = 0,
    apply_changes: bool = False,
) -> dict:
    entries = list_source_entries(sources_dir)
    safe_window = max(1, int(window_jobs))
    threshold = max(0, int(auto_disable_failures))
    by_slug = {row["slug"]: row for row in entries}
    report_rows: list[dict] = []
    disabled_now = 0

    for slug, source_entry in by_slug.items():
        jobs = session.scalars(
            select(ScrapeJobORM)
            .where(ScrapeJobORM.source_slug == slug)
            .order_by(ScrapeJobORM.id.desc())
            .limit(safe_window)
        ).all()
        recent_jobs = len(jobs)
        failed = len([j for j in jobs if j.status == "failed"])
        success = len([j for j in jobs if j.status == "success"])
        consecutive = _consecutive_failures(jobs)
        candidate = bool(source_entry["enabled"] and threshold > 0 and consecutive >= threshold)
        did_disable = False
        if candidate and apply_changes:
            did_disable = set_source_enabled(sources_dir, slug, False)
            if did_disable:
                disabled_now += 1

        success_rate = (success / recent_jobs) if recent_jobs else 0.0
        avg_errors = (sum(int(j.errors) for j in jobs) / recent_jobs) if recent_jobs else 0.0
        avg_leads = (sum(int(j.leads_extracted) for j in jobs) / recent_jobs) if recent_jobs else 0.0
        last_status = jobs[0].status if jobs else "never_run"
        last_finished_at = jobs[0].finished_at.isoformat() if jobs and jobs[0].finished_at else None
        report_rows.append(
            {
                "source_slug": slug,
                "source_name": source_entry.get("name") or slug,
                "enabled": bool(source_entry["enabled"] and not did_disable),
                "stable_pack": bool(source_entry.get("stable_pack", False)),
                "recent_jobs": recent_jobs,
                "success_count": success,
                "failed_count": failed,
                "consecutive_failures": consecutive,
                "success_rate": round(success_rate, 4),
                "avg_errors": round(avg_errors, 2),
                "avg_leads": round(avg_leads, 2),
                "last_status": last_status,
                "last_finished_at": last_finished_at,
                "auto_disable_candidate": candidate,
                "disabled_now": did_disable,
            }
        )

    report_rows.sort(key=lambda row: (row["consecutive_failures"], row["failed_count"]), reverse=True)
    return {
        "sources_count": len(report_rows),
        "window_jobs": safe_window,
        "auto_disable_failures": threshold,
        "disabled_now": disabled_now,
        "items": report_rows,
    }
