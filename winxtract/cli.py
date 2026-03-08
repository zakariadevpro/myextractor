import asyncio
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import typer
import yaml
from sqlalchemy.orm import Session, sessionmaker

from winxtract.core.compliance import find_non_compliant_sources
from winxtract.core.logging import configure_logging, get_logger
from winxtract.core.settings import Settings
from winxtract.core.source_loader import list_source_entries, load_sources, set_source_privacy_profile
from winxtract.orchestrator.job_runner import JobRunner
from winxtract.storage.db import create_engine_from_url, init_db
from winxtract.storage.exporters import export_leads
from winxtract.storage.queue_store import QueueStore
from winxtract.storage.quality import compute_quality_report
from winxtract.storage.source_health import compute_source_health

app = typer.Typer(add_completion=False, help="WinXtract CLI")
PROGRESS_PREFIX = "__progress__:"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalized_source_slug(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized in {"", "*", "all"}:
        return None
    return normalized


def _stable_enabled_source_slugs(sources_dir: str) -> list[str]:
    rows = list_source_entries(sources_dir)
    return [row["slug"] for row in rows if row["enabled"] and bool(row.get("stable_pack", False))]


def _assert_export_compliance(
    cfg: Settings,
    *,
    sources_dir: str,
    source_slug: str | None,
    source_slugs: list[str] | None,
) -> None:
    required = cfg.export_required_privacy_mode.strip().lower()
    if not required:
        return
    invalid = find_non_compliant_sources(
        sources_dir,
        required_privacy_mode=required,
        source_slug=source_slug,
        source_slugs=source_slugs,
    )
    if invalid:
        sample = ", ".join(invalid[:5])
        extra = f" (+{len(invalid)-5})" if len(invalid) > 5 else ""
        raise ValueError(f"Export blocked: sources not compliant with privacy_mode={required}: {sample}{extra}")


def _is_non_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return True
    lowered = f"{type(exc).__name__}: {exc}".strip().lower()
    non_retry_tokens = [
        "robots.txt disallows",
        "anti-bot",
        "captcha",
        "access blocked",
        "access denied",
        "invalid",
        "unsupported task_type",
        "unknown scraper plugin",
        "export blocked",
    ]
    return any(token in lowered for token in non_retry_tokens)


def _run_source_sync(
    cfg: Settings,
    session_factory,
    sources_dir: str,
    source_slug: str | None,
    progress_cb: Callable[[dict], None] | None = None,
) -> str:
    sources = load_sources(sources_dir, source_slug)
    if not sources:
        raise ValueError("No enabled source found")
    runner = JobRunner(cfg)
    stats = asyncio.run(runner.run_sources(sources, session_factory, on_progress=progress_cb))
    return f"Scrape done ({len(stats)} source(s))"


def _run_source_slugs_sync(
    cfg: Settings,
    session_factory,
    sources_dir: str,
    source_slugs: list[str],
    progress_cb: Callable[[dict], None] | None = None,
) -> str:
    slug_set = {slug.strip() for slug in source_slugs if slug and slug.strip()}
    if not slug_set:
        raise ValueError("No source selected")
    sources = [source for source in load_sources(sources_dir) if source.slug in slug_set]
    if not sources:
        raise ValueError("No enabled source found")
    runner = JobRunner(cfg)
    stats = asyncio.run(runner.run_sources(sources, session_factory, on_progress=progress_cb))
    return f"Scrape done ({len(stats)} source(s))"


def _export_sync(
    cfg: Settings,
    engine,
    *,
    sources_dir: str,
    source_slug: str | None,
    source_slugs: list[str] | None,
    export_format: str,
    min_score: int,
    city: str | None,
    has_email: bool | None,
    has_phone: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
    name_contains: str | None,
) -> str:
    _assert_export_compliance(
        cfg,
        sources_dir=sources_dir,
        source_slug=source_slug,
        source_slugs=source_slugs,
    )
    stamp = _now_utc().strftime("%Y%m%d_%H%M%S")
    output = f"exports/leads_{stamp}.{export_format}"
    with Session(engine) as session:
        count = export_leads(
            session,
            output=output,
            fmt=export_format,
            min_score=min_score,
            source_slug=source_slug,
            source_slugs=source_slugs,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            scraped_from=date_from,
            scraped_to=date_to,
            name_contains=name_contains,
        )
    return f"Export done: {count} rows -> {output}"


def _run_then_export_sync(
    cfg: Settings,
    engine,
    session_factory,
    *,
    sources_dir: str,
    source_slug: str | None,
    export_format: str,
    min_score: int,
    city: str | None,
    has_email: bool | None,
    has_phone: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
    name_contains: str | None,
    progress_cb: Callable[[dict], None] | None = None,
) -> str:
    if progress_cb:
        progress_cb({"phase": "scrape", "percent": 2, "label": "Initialisation du scrape"})
    _run_source_sync(cfg, session_factory, sources_dir, source_slug, progress_cb=progress_cb)
    if progress_cb:
        progress_cb({"phase": "export", "percent": 95, "label": "Export en cours"})
    return _export_sync(
        cfg,
        engine,
        sources_dir=sources_dir,
        source_slug=source_slug,
        source_slugs=None,
        export_format=export_format,
        min_score=min_score,
        city=city,
        has_email=has_email,
        has_phone=has_phone,
        date_from=date_from,
        date_to=date_to,
        name_contains=name_contains,
    )


def _run_stable_then_export_sync(
    cfg: Settings,
    engine,
    session_factory,
    *,
    sources_dir: str,
    export_format: str,
    min_score: int,
    city: str | None,
    has_email: bool | None,
    has_phone: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
    name_contains: str | None,
    progress_cb: Callable[[dict], None] | None = None,
) -> str:
    stable_slugs = _stable_enabled_source_slugs(sources_dir)
    if not stable_slugs:
        raise ValueError("No enabled stable-pack source found")
    if progress_cb:
        progress_cb({"phase": "scrape", "percent": 2, "label": "Initialisation du scrape stable"})
    _run_source_slugs_sync(cfg, session_factory, sources_dir, stable_slugs, progress_cb=progress_cb)
    if progress_cb:
        progress_cb({"phase": "export", "percent": 95, "label": "Export en cours"})
    return _export_sync(
        cfg,
        engine,
        sources_dir=sources_dir,
        source_slug=None,
        source_slugs=stable_slugs,
        export_format=export_format,
        min_score=min_score,
        city=city,
        has_email=has_email,
        has_phone=has_phone,
        date_from=date_from,
        date_to=date_to,
        name_contains=name_contains,
    )


def _maybe_auto_disable_unhealthy(cfg: Settings, engine, *, sources_dir: str, logger) -> None:
    threshold = max(0, int(cfg.source_health_auto_disable_failures))
    if threshold <= 0:
        return
    with Session(engine) as session:
        report = compute_source_health(
            session,
            sources_dir=sources_dir,
            window_jobs=max(1, int(cfg.source_health_window_jobs)),
            auto_disable_failures=threshold,
            apply_changes=True,
        )
    if report["disabled_now"] > 0:
        logger.warning(
            "sources_auto_disabled",
            disabled_now=report["disabled_now"],
            threshold=threshold,
            window_jobs=int(cfg.source_health_window_jobs),
        )


def _execute_queue_task(
    cfg: Settings,
    engine,
    session_factory,
    *,
    sources_dir: str,
    task_type: str,
    payload: dict,
    progress_cb: Callable[[dict], None] | None = None,
) -> str:
    source_slug = _normalized_source_slug(payload.get("source_slug"))
    export_format = (payload.get("format") or payload.get("export_format") or "csv").strip().lower()
    if export_format not in {"csv", "json", "xlsx"}:
        raise ValueError("Invalid export format")

    min_score = max(0, min(100, int(payload.get("min_score", 0))))
    city = payload.get("city")
    has_email = payload.get("has_email")
    has_phone = payload.get("has_phone")
    date_from = _parse_iso(payload.get("date_from"))
    date_to = _parse_iso(payload.get("date_to"))
    name_contains = payload.get("name_contains")

    if task_type == "run":
        if progress_cb:
            progress_cb({"phase": "scrape", "percent": 1, "label": "Run en cours"})
        return _run_source_sync(cfg, session_factory, sources_dir, source_slug, progress_cb=progress_cb)
    if task_type == "export":
        if progress_cb:
            progress_cb({"phase": "export", "percent": 90, "label": "Export en cours"})
        return _export_sync(
            cfg,
            engine,
            sources_dir=sources_dir,
            source_slug=source_slug,
            source_slugs=None,
            export_format=export_format,
            min_score=min_score,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            date_from=date_from,
            date_to=date_to,
            name_contains=name_contains,
        )
    if task_type in {"run_export", "run_export_all", "scheduled_run_export", "scheduled_run_export_manual"}:
        return _run_then_export_sync(
            cfg,
            engine,
            session_factory,
            sources_dir=sources_dir,
            source_slug=source_slug,
            export_format=export_format,
            min_score=min_score,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            date_from=date_from,
            date_to=date_to,
            name_contains=name_contains,
            progress_cb=progress_cb,
        )
    if task_type == "run_export_stable":
        return _run_stable_then_export_sync(
            cfg,
            engine,
            session_factory,
            sources_dir=sources_dir,
            export_format=export_format,
            min_score=min_score,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            date_from=date_from,
            date_to=date_to,
            name_contains=name_contains,
            progress_cb=progress_cb,
        )
    raise ValueError(f"Unsupported task_type: {task_type}")


def _load_source_catalog(path: str) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    items = raw.get("catalog", [])
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


@app.command("init-db")
def init_db_command(db_url: str = typer.Option(None, help="Database URL")) -> None:
    cfg = Settings()
    configure_logging(cfg.log_level)
    logger = get_logger("cli")
    url = db_url or cfg.db_url
    engine = create_engine_from_url(url)
    Path("data").mkdir(parents=True, exist_ok=True)
    init_db(engine)
    logger.info("db_initialized", db_url=url)


@app.command("run")
def run_command(
    sources_dir: str = typer.Option("config/sources", help="Sources YAML directory"),
    source: str | None = typer.Option(None, help="Run only one source slug"),
    db_url: str = typer.Option(None, help="Database URL override"),
) -> None:
    cfg = Settings()
    if db_url:
        cfg.db_url = db_url
    configure_logging(cfg.log_level)
    logger = get_logger("cli")

    engine = create_engine_from_url(cfg.db_url)
    init_db(engine)
    sources = load_sources(sources_dir, source)
    if not sources:
        raise typer.BadParameter("No enabled sources found")

    runner = JobRunner(cfg)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    stats = asyncio.run(runner.run_sources(sources, session_factory))
    logger.info("run_done", sources=len(stats), stats={k: v.model_dump() for k, v in stats.items()})


@app.command("export")
def export_command(
    format: str = typer.Option(..., "--format", help="csv|json|xlsx"),
    output: str = typer.Option(..., help="Output file path"),
    min_score: int = typer.Option(0, help="Minimum score"),
    source: str | None = typer.Option(None, help="Optional source slug filter"),
    city: str | None = typer.Option(None, help="Optional city filter (exact match)"),
    has_email: str | None = typer.Option(None, help="Filter leads with email: true|false"),
    has_phone: str | None = typer.Option(None, help="Filter leads with phone: true|false"),
    date_from: str | None = typer.Option(None, help="ISO datetime lower bound (inclusive)"),
    date_to: str | None = typer.Option(None, help="ISO datetime upper bound (inclusive)"),
    name_contains: str | None = typer.Option(None, help="Filter leads by name substring"),
    db_url: str = typer.Option(None, help="Database URL override"),
    sources_dir: str = typer.Option("config/sources", help="Sources YAML directory"),
) -> None:
    cfg = Settings()
    if db_url:
        cfg.db_url = db_url
    configure_logging(cfg.log_level)
    logger = get_logger("cli")

    def _parse_iso(value: str | None, field_name: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception as exc:
            raise typer.BadParameter(f"Invalid {field_name}. Use ISO format.") from exc

    def _parse_tristate(value: str | None, field_name: str) -> bool | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        raise typer.BadParameter(f"Invalid {field_name}. Use true|false.")

    parsed_from = _parse_iso(date_from, "date_from")
    parsed_to = _parse_iso(date_to, "date_to")
    parsed_has_email = _parse_tristate(has_email, "has_email")
    parsed_has_phone = _parse_tristate(has_phone, "has_phone")
    _assert_export_compliance(
        cfg,
        sources_dir=sources_dir,
        source_slug=source,
        source_slugs=None,
    )

    engine = create_engine_from_url(cfg.db_url)
    with Session(engine) as session:
        count = export_leads(
            session,
            output=output,
            fmt=format,
            min_score=min_score,
            source_slug=source,
            city=city,
            has_email=parsed_has_email,
            has_phone=parsed_has_phone,
            scraped_from=parsed_from,
            scraped_to=parsed_to,
            name_contains=name_contains,
        )
    logger.info(
        "export_done",
        format=format,
        output=output,
        count=count,
        filters={
            "source": source,
            "city": city,
            "has_email": parsed_has_email,
            "has_phone": parsed_has_phone,
            "date_from": date_from,
            "date_to": date_to,
            "name_contains": name_contains,
            "min_score": min_score,
        },
    )


@app.command("ui")
def ui_command(
    host: str = typer.Option("127.0.0.1", help="Host"),
    port: int = typer.Option(8787, help="Port"),
) -> None:
    try:
        import uvicorn
    except Exception as exc:
        raise typer.BadParameter(
            "UI dependencies missing. Run: python -m pip install -e .[api]"
        ) from exc

    from winxtract.ui import create_ui_app

    uvicorn.run(create_ui_app(), host=host, port=port)


@app.command("quality-report")
def quality_report_command(
    output: str | None = typer.Option(None, help="Optional JSON output path"),
    source: str | None = typer.Option(None, help="Optional source slug filter"),
    db_url: str = typer.Option(None, help="Database URL override"),
) -> None:
    cfg = Settings()
    if db_url:
        cfg.db_url = db_url
    configure_logging(cfg.log_level)
    logger = get_logger("cli")

    engine = create_engine_from_url(cfg.db_url)
    with Session(engine) as session:
        report = compute_quality_report(session, source_slug=source)

    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("quality_report_written", output=str(out), source=source)
    else:
        logger.info("quality_report", source=source, report=report)


@app.command("privacy-profile")
def privacy_profile_command(
    profile: str = typer.Option(..., help="none|b2c_conforme|b2c_etendu"),
    source: str | None = typer.Option(None, help="Optional source slug, default=all"),
    sources_dir: str = typer.Option("config/sources", help="Sources YAML directory"),
) -> None:
    cfg = Settings()
    configure_logging(cfg.log_level)
    logger = get_logger("cli")
    target = source or "*"
    try:
        updated = set_source_privacy_profile(sources_dir, target, profile)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    logger.info("privacy_profile_updated", profile=profile, source=target, updated=updated)


@app.command("source-health")
def source_health_command(
    sources_dir: str = typer.Option("config/sources", help="Sources YAML directory"),
    window_jobs: int = typer.Option(10, help="Jobs window per source"),
    auto_disable_failures: int = typer.Option(0, help="Disable source after N consecutive failures"),
    apply_changes: bool = typer.Option(False, help="Apply source disable immediately"),
    output: str | None = typer.Option(None, help="Optional JSON output path"),
    db_url: str = typer.Option(None, help="Database URL override"),
) -> None:
    cfg = Settings()
    if db_url:
        cfg.db_url = db_url
    configure_logging(cfg.log_level)
    logger = get_logger("cli")

    engine = create_engine_from_url(cfg.db_url)
    init_db(engine)
    with Session(engine) as session:
        report = compute_source_health(
            session,
            sources_dir=sources_dir,
            window_jobs=window_jobs,
            auto_disable_failures=auto_disable_failures,
            apply_changes=apply_changes,
        )
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("source_health_written", output=str(out))
    else:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command("queue-list")
def queue_list_command(
    status: str | None = typer.Option(None, help="queued|running|success|failed|dead"),
    limit: int = typer.Option(100, help="Limit"),
    offset: int = typer.Option(0, help="Offset"),
    db_url: str = typer.Option(None, help="Database URL override"),
) -> None:
    cfg = Settings()
    if db_url:
        cfg.db_url = db_url
    configure_logging(cfg.log_level)
    engine = create_engine_from_url(cfg.db_url)
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue_store = QueueStore(session_factory)
    rows = queue_store.list_tasks(status=status, limit=limit, offset=offset)
    payload = [
        {
            "id": row.id,
            "task_type": row.task_type,
            "status": row.status,
            "attempts": row.attempts,
            "max_attempts": row.max_attempts,
            "worker_id": row.worker_id,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "payload": row.payload,
        }
        for row in rows
    ]
    typer.echo(json.dumps({"count": len(payload), "items": payload}, ensure_ascii=False, indent=2))


@app.command("queue-worker")
def queue_worker_command(
    sources_dir: str = typer.Option("config/sources", help="Sources YAML directory"),
    once: bool = typer.Option(False, help="Process at most one task then exit"),
    poll_seconds: float = typer.Option(0.0, help="Worker polling interval, 0=use settings"),
    worker_id: str | None = typer.Option(None, help="Optional worker id"),
    db_url: str = typer.Option(None, help="Database URL override"),
) -> None:
    cfg = Settings()
    if db_url:
        cfg.db_url = db_url
    configure_logging(cfg.log_level)
    logger = get_logger("cli.worker")

    engine = create_engine_from_url(cfg.db_url)
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue_store = QueueStore(session_factory)
    resolved_worker = worker_id or f"worker-{uuid4().hex[:8]}"
    sleep_for = float(poll_seconds if poll_seconds > 0 else cfg.worker_poll_seconds)
    sleep_for = max(0.2, sleep_for)

    logger.info(
        "queue_worker_started",
        worker_id=resolved_worker,
        once=once,
        poll_seconds=sleep_for,
        sources_dir=sources_dir,
    )

    while True:
        task = queue_store.claim_next(worker_id=resolved_worker)
        if task is None:
            if once:
                break
            time.sleep(sleep_for)
            continue

        try:
            def _progress(payload: dict) -> None:
                queue_store.update_progress(
                    task.id,
                    f"{PROGRESS_PREFIX}{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}",
                )

            message = _execute_queue_task(
                cfg,
                engine,
                session_factory,
                sources_dir=sources_dir,
                task_type=task.task_type,
                payload=task.payload,
                progress_cb=_progress,
            )
            queue_store.mark_success(task.id, message=message)
            _maybe_auto_disable_unhealthy(cfg, engine, sources_dir=sources_dir, logger=logger)
            logger.info(
                "queue_task_success",
                task_id=task.id,
                task_type=task.task_type,
                attempts=task.attempts,
                worker_id=resolved_worker,
            )
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            non_retryable = _is_non_retryable_error(exc)
            terminal = int(task.attempts) >= int(task.max_attempts) or non_retryable
            retry_delay = 0.0
            if terminal:
                queue_store.mark_dead(task.id, error_message=error_message)
            else:
                backoff_base = max(0.5, float(cfg.queue_retry_backoff_base_seconds))
                backoff_max = max(backoff_base, float(cfg.queue_retry_backoff_max_seconds))
                retry_delay = min(backoff_max, backoff_base * (2 ** max(0, task.attempts - 1)))
                queue_store.mark_failure(
                    task.id,
                    error_message=error_message,
                    retry_delay_seconds=retry_delay,
                )
            _maybe_auto_disable_unhealthy(cfg, engine, sources_dir=sources_dir, logger=logger)
            logger.error(
                "queue_task_dead" if terminal else "queue_task_retry",
                task_id=task.id,
                task_type=task.task_type,
                attempts=task.attempts,
                max_attempts=task.max_attempts,
                retry_delay_seconds=retry_delay,
                terminal=terminal,
                non_retryable=non_retryable,
                worker_id=resolved_worker,
                error=error_message,
                trace=traceback.format_exc(),
            )

        if once:
            break


@app.command("source-catalog")
def source_catalog_command(
    catalog_file: str = typer.Option("config/source_catalog.yaml", help="Catalog YAML path"),
    status: str | None = typer.Option(None, help="stable|candidate"),
    family: str | None = typer.Option(None, help="Filter family"),
    as_json: bool = typer.Option(False, help="Output JSON"),
) -> None:
    rows = _load_source_catalog(catalog_file)
    if status:
        normalized_status = status.strip().lower()
        rows = [row for row in rows if str(row.get("status", "")).strip().lower() == normalized_status]
    if family:
        normalized_family = family.strip().lower()
        rows = [row for row in rows if str(row.get("family", "")).strip().lower() == normalized_family]

    if as_json:
        typer.echo(json.dumps({"count": len(rows), "items": rows}, ensure_ascii=False, indent=2))
        return

    typer.echo(f"count={len(rows)}")
    for row in rows:
        typer.echo(
            f"- {row.get('slug')} | {row.get('label')} | family={row.get('family')} | "
            f"status={row.get('status')} | yaml={row.get('yaml')}"
        )


@app.command("load-test")
def load_test_command(
    base_url: str = typer.Option("http://127.0.0.1:8787", help="WinXtract UI base URL"),
    action: str = typer.Option("export", help="run|export|run-export|run-export-stable"),
    requests_count: int = typer.Option(20, help="Total requests"),
    concurrency: int = typer.Option(5, help="Concurrent requests"),
    source_slug: str = typer.Option("*", help="Source slug or *"),
    api_token: str = typer.Option("", help="Optional API token"),
) -> None:
    action_map = {
        "run": "/api/v1/actions/run",
        "export": "/api/v1/actions/export",
        "run-export": "/api/v1/actions/run-export",
        "run-export-stable": "/api/v1/actions/run-export-stable",
    }
    action_key = action.strip().lower()
    endpoint = action_map.get(action_key)
    if endpoint is None:
        raise typer.BadParameter("action must be run|export|run-export|run-export-stable")

    safe_requests = max(1, requests_count)
    safe_concurrency = max(1, min(concurrency, safe_requests))
    payload: dict = {"source_slug": source_slug}
    if action_key in {"export", "run-export", "run-export-stable"}:
        payload.update({"export_format": "csv", "min_score": 0})
    if action_key == "run-export-stable":
        payload.pop("source_slug", None)

    headers = {"Content-Type": "application/json"}
    if api_token:
        headers["X-API-Key"] = api_token

    async def _runner() -> dict:
        semaphore = asyncio.Semaphore(safe_concurrency)
        latencies_ms: list[float] = []
        statuses: dict[int, int] = {}
        errors = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            async def _one() -> None:
                nonlocal errors
                async with semaphore:
                    t0 = time.perf_counter()
                    try:
                        resp = await client.post(f"{base_url}{endpoint}", json=payload, headers=headers)
                        elapsed = (time.perf_counter() - t0) * 1000.0
                        latencies_ms.append(elapsed)
                        statuses[resp.status_code] = statuses.get(resp.status_code, 0) + 1
                    except Exception:
                        errors += 1

            await asyncio.gather(*[_one() for _ in range(safe_requests)])

        latencies_ms.sort()
        p50 = latencies_ms[int(0.5 * (len(latencies_ms) - 1))] if latencies_ms else 0.0
        p95 = latencies_ms[int(0.95 * (len(latencies_ms) - 1))] if latencies_ms else 0.0
        return {
            "action": action_key,
            "endpoint": endpoint,
            "requests": safe_requests,
            "concurrency": safe_concurrency,
            "errors": errors,
            "status_counts": statuses,
            "latency_ms_avg": round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0,
            "latency_ms_p50": round(p50, 2),
            "latency_ms_p95": round(p95, 2),
        }

    report = asyncio.run(_runner())
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
