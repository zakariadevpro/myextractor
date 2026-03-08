import asyncio
import inspect
import json
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from winxtract.core.logging import configure_logging, get_logger
from winxtract.core.scheduler_store import list_schedules, set_schedule_enabled, upsert_schedule
from winxtract.core.settings import Settings
from winxtract.core.compliance import find_non_compliant_sources
from winxtract.core.source_loader import (
    list_source_entries,
    load_sources,
    set_source_enabled,
    set_source_privacy_profile,
)
from winxtract.orchestrator.job_runner import JobRunner
from winxtract.storage.db import ErrorLogORM, LeadORM, QueueTaskORM, ScrapeJobORM, create_engine_from_url, init_db
from winxtract.storage.exporters import export_leads
from winxtract.storage.quality import compute_quality_report
from winxtract.storage.queue_store import QueueStore
from winxtract.storage.source_health import compute_source_health


class RunActionRequest(BaseModel):
    source_slug: str | None = None


class ExportActionRequest(BaseModel):
    source_slug: str | None = None
    export_format: str = "csv"
    min_score: int = 0
    city: str | None = None
    has_email: bool | None = None
    has_phone: bool | None = None
    date_from: str | None = None
    date_to: str | None = None
    name_contains: str | None = None


class RequeueBatchRequest(BaseModel):
    task_ids: list[str] = []
    status: str = "all"
    task_type: str | None = None
    source_slug: str | None = None
    message_contains: str | None = None
    limit: int = 100


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_ui_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)
    logger = get_logger("ui")

    engine = create_engine_from_url(settings.db_url)
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue_store = QueueStore(session_factory)
    task_backend = settings.task_backend.strip().lower()
    if task_backend not in {"thread", "db_queue"}:
        task_backend = "thread"

    base_dir = Path(__file__).resolve().parent
    exports_dir = Path("exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    schedule_file = "config/schedules.yaml"
    task_lock = threading.Lock()
    task_store: dict[str, dict] = {}
    task_order: deque[str] = deque(maxlen=200)
    progress_prefix = "__progress__:"
    api_rate_lock = threading.Lock()
    api_rate_buckets: dict[str, tuple[int, int]] = {}
    schedule_lock = threading.Lock()
    schedule_next_due: dict[str, datetime] = {}
    schedule_running: set[str] = set()
    schedule_stop = threading.Event()
    schedule_thread: threading.Thread | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal schedule_thread
        if not schedule_thread or not schedule_thread.is_alive():
            schedule_stop.clear()
            schedule_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="winxtract-scheduler")
            schedule_thread.start()
        try:
            yield
        finally:
            schedule_stop.set()
            if schedule_thread and schedule_thread.is_alive():
                schedule_thread.join(timeout=2)

    app = FastAPI(title="WinXtract UI", lifespan=lifespan)
    templates = Jinja2Templates(directory=str(base_dir / "templates"))

    def static_url(asset_path: str) -> str:
        cleaned = (asset_path or "").strip().lstrip("/")
        if not cleaned:
            return "/static"
        asset_file = base_dir / "static" / cleaned
        try:
            version = int(asset_file.stat().st_mtime)
        except OSError:
            version = int(time.time())
        return f"/static/{cleaned}?v={version}"

    templates.env.globals["static_url"] = static_url
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.mount("/exports-files", StaticFiles(directory=str(exports_dir)), name="exports_files")

    def _extract_api_token(request: Request) -> str:
        header_token = (request.headers.get("X-API-Key") or "").strip()
        if header_token:
            return header_token
        auth = (request.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""

    def _api_identity(request: Request) -> str:
        token = _extract_api_token(request)
        if token:
            return f"token:{token}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    @app.middleware("http")
    async def api_security_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1") and path != "/api/v1/health":
            if settings.api_token:
                provided = _extract_api_token(request)
                if provided != settings.api_token:
                    return JSONResponse(status_code=401, content={"detail": "invalid or missing API token"})

            limit = max(1, int(settings.api_rate_limit_per_minute))
            now_minute = int(time.time() // 60)
            identity = _api_identity(request)
            with api_rate_lock:
                for key, (bucket_minute, _) in list(api_rate_buckets.items()):
                    if bucket_minute < now_minute - 2:
                        api_rate_buckets.pop(key, None)
                bucket = api_rate_buckets.get(identity)
                if not bucket or bucket[0] != now_minute:
                    count = 1
                    api_rate_buckets[identity] = (now_minute, count)
                else:
                    count = bucket[1] + 1
                    api_rate_buckets[identity] = (now_minute, count)
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "rate limit exceeded"},
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)

    def _new_task(task_type: str, payload: dict) -> str:
        task_id = uuid4().hex[:10]
        with task_lock:
            task_store[task_id] = {
                "id": task_id,
                "type": task_type,
                "status": "queued",
                "payload": payload,
                "message": "",
                "created_at": now_utc(),
                "started_at": None,
                "finished_at": None,
                "attempts": 0,
                "max_attempts": 1,
                "worker_id": None,
                "progress": None,
            }
            task_order.appendleft(task_id)
        return task_id

    def _new_db_task(task_type: str, payload: dict) -> str:
        row = queue_store.enqueue(task_type=task_type, payload=payload)
        return str(row.id)

    def _set_task(task_id: str, **kwargs) -> None:
        with task_lock:
            task = task_store.get(task_id)
            if not task:
                return
            task.update(kwargs)

    def _decode_progress_message(raw_message: str | None) -> tuple[dict | None, str]:
        message = (raw_message or "").strip()
        if not message.startswith(progress_prefix):
            return None, message
        payload = message[len(progress_prefix) :]
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed, ""
        except Exception:
            return None, message
        return None, message

    def _decorate_task_progress(status: str, progress: dict | None, message: str) -> tuple[int, str]:
        safe_progress = progress or {}
        if safe_progress:
            pct = int(max(0, min(100, safe_progress.get("percent", 0) or 0)))
            phase = str(safe_progress.get("phase", "")).strip().lower()
            label = str(safe_progress.get("label", "")).strip()
            if label:
                return pct, label
            if phase == "scrape":
                done = int(safe_progress.get("sources_done", 0) or 0)
                total = int(safe_progress.get("sources_total", 0) or 0)
                pages = int(safe_progress.get("pages_scraped", 0) or 0)
                leads = int(safe_progress.get("leads_extracted", 0) or 0)
                errors = int(safe_progress.get("errors", 0) or 0)
                duration = float(safe_progress.get("duration_seconds", 0.0) or 0.0)
                return (
                    pct,
                    f"Scrape {done}/{total} sources | pages {pages} | leads {leads} | errors {errors} | {duration:.0f}s",
                )
            if phase == "export":
                return pct, "Export en cours"
            return pct, "En cours"

        normalized = (status or "").lower()
        if normalized == "queued":
            return 0, "En attente"
        if normalized == "running":
            return 10, "En cours"
        if normalized == "success":
            return 100, message or "Terminee"
        if normalized in {"failed", "dead"}:
            return 100, message or "Echec"
        return 0, message or "-"

    def _memory_recent_tasks(limit: int = 20) -> list[dict]:
        with task_lock:
            ids = list(task_order)[:limit]
            return [task_store[i] for i in ids if i in task_store]

    def _db_task_to_dict(task) -> dict:
        progress, clean_message = _decode_progress_message(task.message)
        progress_percent, progress_label = _decorate_task_progress(task.status, progress, clean_message)
        return {
            "id": str(task.id),
            "type": task.task_type,
            "status": task.status,
            "payload": task.payload,
            "message": clean_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "attempts": task.attempts,
            "max_attempts": task.max_attempts,
            "worker_id": task.worker_id,
            "progress": progress,
            "progress_percent": progress_percent,
            "progress_label": progress_label,
        }

    def _recent_tasks(limit: int = 20) -> list[dict]:
        if task_backend == "db_queue":
            rows = queue_store.list_tasks(limit=limit)
            return [_db_task_to_dict(row) for row in rows]
        return _memory_recent_tasks(limit)

    def _task_by_id(task_id: str) -> dict | None:
        if task_backend == "db_queue":
            try:
                parsed = int(task_id)
            except Exception:
                return None
            row = queue_store.get_task(parsed)
            return _db_task_to_dict(row) if row else None
        with task_lock:
            return task_store.get(task_id)

    def _run_source_sync(selected: str | None, progress_cb: Callable[[dict], None] | None = None) -> str:
        sources = load_sources("config/sources", selected)
        if not sources:
            raise ValueError("No enabled source found")
        runner = JobRunner(settings)
        stats = asyncio.run(runner.run_sources(sources, session_factory, on_progress=progress_cb))
        logger.info("ui_run_done", stats={k: v.model_dump() for k, v in stats.items()})
        return f"Scrape done ({len(stats)} source(s))"

    def _run_source_slugs_sync(source_slugs: list[str], progress_cb: Callable[[dict], None] | None = None) -> str:
        if not source_slugs:
            raise ValueError("No source selected")
        slug_set = {slug.strip() for slug in source_slugs if slug and slug.strip()}
        if not slug_set:
            raise ValueError("No source selected")
        sources = [source for source in load_sources("config/sources") if source.slug in slug_set]
        if not sources:
            raise ValueError("No enabled source found for stable pack")
        runner = JobRunner(settings)
        stats = asyncio.run(runner.run_sources(sources, session_factory, on_progress=progress_cb))
        logger.info("ui_run_done", stats={k: v.model_dump() for k, v in stats.items()})
        return f"Scrape done ({len(stats)} source(s))"

    def _export_sync(
        selected: str | None,
        export_format: str,
        min_score: int,
        *,
        source_slugs: list[str] | None = None,
        city: str | None = None,
        has_email: bool | None = None,
        has_phone: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        name_contains: str | None = None,
        progress_cb: Callable[[dict], None] | None = None,
    ) -> str:
        if progress_cb:
            progress_cb({"phase": "export", "percent": 90, "label": "Export en cours"})
        _assert_export_compliance(selected, source_slugs)
        stamp = now_utc().strftime("%Y%m%d_%H%M%S")
        output = f"exports/leads_{stamp}.{export_format}"
        with Session(engine) as session:
            count = export_leads(
                session,
                output=output,
                fmt=export_format,
                min_score=min_score,
                source_slug=selected,
                source_slugs=source_slugs,
                city=city,
                has_email=has_email,
                has_phone=has_phone,
                scraped_from=date_from,
                scraped_to=date_to,
                name_contains=name_contains,
            )
        if progress_cb:
            progress_cb({"phase": "export", "percent": 99, "label": f"Export termine ({count} lignes)"})
        return f"Export done: {count} rows -> {output}"

    def _execute_task(task_id: str, fn) -> None:
        _set_task(
            task_id,
            status="running",
            started_at=now_utc(),
            progress={"phase": "setup", "percent": 1, "label": "Initialisation"},
        )

        def _progress(payload: dict) -> None:
            if not isinstance(payload, dict):
                return
            _set_task(task_id, progress=payload)

        try:
            signature = inspect.signature(fn)
            if len(signature.parameters) >= 1:
                msg = fn(_progress)
            else:
                msg = fn()
            _set_task(
                task_id,
                status="success",
                message=msg,
                finished_at=now_utc(),
                progress={"phase": "done", "percent": 100, "label": "Terminee"},
            )
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.error("ui_task_failed", task_id=task_id, error=err, trace=traceback.format_exc())
            _set_task(
                task_id,
                status="failed",
                message=err,
                finished_at=now_utc(),
                progress={"phase": "failed", "percent": 100, "label": err},
            )
        finally:
            _auto_disable_unhealthy_sources()

    def _auto_disable_unhealthy_sources() -> None:
        threshold = max(0, int(settings.source_health_auto_disable_failures))
        if threshold <= 0:
            return
        window_jobs = max(1, int(settings.source_health_window_jobs))
        with Session(engine) as session:
            report = compute_source_health(
                session,
                sources_dir="config/sources",
                window_jobs=window_jobs,
                auto_disable_failures=threshold,
                apply_changes=True,
            )
        if report["disabled_now"] > 0:
            logger.warning(
                "sources_auto_disabled",
                disabled_now=report["disabled_now"],
                threshold=threshold,
                window_jobs=window_jobs,
            )

    def _source_to_dict(row: dict) -> dict:
        return {
            "slug": row["slug"],
            "name": row.get("name") or row["slug"],
            "scraper": row["scraper"],
            "enabled": row["enabled"],
            "stable_pack": bool(row.get("stable_pack", False)),
            "privacy_mode": row.get("privacy_mode", "none"),
            "privacy_profile": row.get("privacy_profile", ""),
            "path": row["path"],
        }

    def _job_to_dict(job: ScrapeJobORM) -> dict:
        return {
            "id": job.id,
            "source_slug": job.source_slug,
            "status": job.status,
            "pages_scraped": job.pages_scraped,
            "leads_extracted": job.leads_extracted,
            "errors": job.errors,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }

    def _lead_to_dict(lead: LeadORM) -> dict:
        return {
            "id": lead.id,
            "source_slug": lead.source_slug,
            "name": lead.name,
            "city": lead.city,
            "category": lead.category,
            "website": lead.website,
            "emails": lead.emails,
            "phones": lead.phones,
            "address": lead.address,
            "description": lead.description,
            "page_url": lead.page_url,
            "score": lead.score,
            "fingerprint": lead.fingerprint,
            "scraped_at": lead.scraped_at,
        }

    def _error_to_dict(err: ErrorLogORM) -> dict:
        return {
            "id": err.id,
            "source_slug": err.source_slug,
            "page_url": err.page_url,
            "error_type": err.error_type,
            "message": err.message,
            "created_at": err.created_at,
        }

    def _task_to_dict(task: dict) -> dict:
        progress = task.get("progress") if isinstance(task.get("progress"), dict) else None
        progress_percent, progress_label = _decorate_task_progress(task["status"], progress, task["message"])
        return {
            "id": task["id"],
            "type": task["type"],
            "status": task["status"],
            "payload": task["payload"],
            "message": task["message"],
            "created_at": task["created_at"],
            "started_at": task["started_at"],
            "finished_at": task["finished_at"],
            "attempts": task.get("attempts"),
            "max_attempts": task.get("max_attempts"),
            "worker_id": task.get("worker_id"),
            "progress": progress,
            "progress_percent": progress_percent,
            "progress_label": progress_label,
        }

    def _source_label_map(source_entries: list[dict]) -> dict[str, str]:
        return {row["slug"]: (row.get("name") or row["slug"]) for row in source_entries}

    def _stable_enabled_source_slugs() -> list[str]:
        rows = list_source_entries("config/sources")
        return [row["slug"] for row in rows if row["enabled"] and bool(row.get("stable_pack", False))]

    def _list_export_files(limit: int = 20) -> list[dict]:
        safe_limit = max(1, min(int(limit), 500))
        return sorted(
            [
                {
                    "name": file.name,
                    "size": file.stat().st_size,
                    "mtime": datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc),
                }
                for file in exports_dir.glob("leads_*.*")
                if file.is_file()
            ],
            key=lambda x: x["mtime"],
            reverse=True,
        )[:safe_limit]

    def _safe_next_page(next_page: str | None, fallback: str) -> str:
        candidate = (next_page or "").strip()
        if not candidate:
            return fallback
        if not candidate.startswith("/") or candidate.startswith("//"):
            return fallback
        return candidate

    def _redirect_with_msg(target: str, message: str) -> RedirectResponse:
        sep = "&" if "?" in target else "?"
        return RedirectResponse(url=f"{target}{sep}msg={quote_plus(message)}", status_code=303)

    def _dead_statuses(status: str | None) -> tuple[str, ...]:
        normalized = (status or "").strip().lower()
        if normalized in {"dead", "failed"}:
            return (normalized,)
        return ("dead", "failed")

    def _safe_dead_filter_status(status: str | None) -> str:
        normalized = (status or "").strip().lower()
        if normalized in {"dead", "failed", "all"}:
            return normalized
        return "all"

    def _safe_source_filter(value: str | None) -> str:
        normalized = (value or "").strip()
        if normalized in {"", "*", "all"}:
            return ""
        return normalized

    def _parse_task_ids(task_ids: list[str]) -> list[int]:
        parsed: list[int] = []
        seen: set[int] = set()
        for raw in task_ids:
            token = (raw or "").strip()
            if not token:
                continue
            try:
                number = int(token)
            except Exception:
                continue
            if number <= 0 or number in seen:
                continue
            seen.add(number)
            parsed.append(number)
        return parsed

    def _filtered_dead_tasks(
        *,
        status: str,
        task_type: str | None,
        source_slug: str | None,
        message_contains: str | None,
        limit: int,
    ) -> list[dict]:
        if task_backend != "db_queue":
            return []

        safe_limit = max(1, min(int(limit), 500))
        statuses = _dead_statuses(status)
        rows = queue_store.list_tasks(statuses=statuses, limit=max(200, min(1000, safe_limit * 5)))
        type_filter = (task_type or "").strip().lower()
        source_filter = _safe_source_filter(source_slug).lower()
        message_filter = (message_contains or "").strip().lower()

        items: list[dict] = []
        for row in rows:
            item = _db_task_to_dict(row)
            if type_filter and type_filter not in str(item.get("type", "")).lower():
                continue
            payload = item.get("payload") or {}
            payload_source = str(payload.get("source_slug") or "").strip().lower()
            if source_filter and payload_source != source_filter:
                continue
            message = str(item.get("message") or "").lower()
            if message_filter and message_filter not in message:
                continue
            items.append(item)
            if len(items) >= safe_limit:
                break
        return items

    def _requeue_many(task_ids: list[int]) -> tuple[int, list[int]]:
        requeued_ids: list[int] = []
        for task_id in task_ids:
            replay = queue_store.requeue_task(task_id, allowed_statuses=("dead", "failed"))
            if replay is not None:
                requeued_ids.append(int(replay.id))
        return len(requeued_ids), requeued_ids

    def _dashboard_snapshot() -> dict:
        source_entries = list_source_entries("config/sources")
        enabled_sources = [entry for entry in source_entries if entry["enabled"]]
        stable_enabled_sources = [entry for entry in enabled_sources if bool(entry.get("stable_pack", False))]
        source_labels = _source_label_map(source_entries)
        schedules = list_schedules(schedule_file)
        active_schedules = len([s for s in schedules if s["enabled"]])
        with Session(engine) as session:
            total_leads = session.scalar(select(func.count()).select_from(LeadORM)) or 0
            total_jobs = session.scalar(select(func.count()).select_from(ScrapeJobORM)) or 0
            total_errors = session.scalar(select(func.count()).select_from(ErrorLogORM)) or 0
            recent_jobs = (
                session.scalars(select(ScrapeJobORM).order_by(ScrapeJobORM.id.desc()).limit(12)).all()
            )
        return {
            "source_entries": source_entries,
            "sources": enabled_sources,
            "source_labels": source_labels,
            "active_sources_count": len(enabled_sources),
            "stable_sources_count": len(stable_enabled_sources),
            "active_schedules_count": active_schedules,
            "total_leads": total_leads,
            "total_jobs": total_jobs,
            "total_errors": total_errors,
            "recent_jobs": recent_jobs,
            "task_backend": task_backend,
        }

    def _assert_export_compliance(selected: str | None, source_slugs: list[str] | None = None) -> None:
        required = settings.export_required_privacy_mode.strip().lower()
        if not required:
            return
        invalid = find_non_compliant_sources(
            "config/sources",
            required_privacy_mode=required,
            source_slug=selected,
            source_slugs=source_slugs,
        )
        if invalid:
            sample = ", ".join(invalid[:5])
            extra = f" (+{len(invalid)-5})" if len(invalid) > 5 else ""
            raise ValueError(
                f"Export blocked: sources not compliant with privacy_mode={required}: {sample}{extra}"
            )

    def _queue_thread_task(task_type: str, payload: dict, fn) -> str:
        task_id = _new_task(task_type, payload)
        thread = threading.Thread(target=_execute_task, args=(task_id, fn), daemon=True)
        thread.start()
        return task_id

    def _queue_task(task_type: str, payload: dict, fn=None) -> str:
        if task_backend == "db_queue":
            return _new_db_task(task_type, payload)
        if fn is None:
            raise ValueError("Thread backend requires a callable")
        return _queue_thread_task(task_type, payload, fn)

    def _run_then_export_sync(
        selected: str | None,
        export_format: str,
        min_score: int,
        *,
        city: str | None = None,
        has_email: bool | None = None,
        has_phone: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        name_contains: str | None = None,
        progress_cb: Callable[[dict], None] | None = None,
    ) -> str:
        if progress_cb:
            progress_cb({"phase": "scrape", "percent": 2, "label": "Initialisation du scrape"})
        _run_source_sync(selected, progress_cb=progress_cb)
        if progress_cb:
            progress_cb({"phase": "export", "percent": 95, "label": "Export en cours"})
        return _export_sync(
            selected,
            export_format,
            min_score,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            date_from=date_from,
            date_to=date_to,
            name_contains=name_contains,
        )

    def _run_stable_then_export_sync(
        export_format: str,
        min_score: int,
        *,
        city: str | None = None,
        has_email: bool | None = None,
        has_phone: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        name_contains: str | None = None,
        progress_cb: Callable[[dict], None] | None = None,
    ) -> str:
        stable_slugs = _stable_enabled_source_slugs()
        if not stable_slugs:
            raise ValueError("No enabled stable-pack source found")
        if progress_cb:
            progress_cb({"phase": "scrape", "percent": 2, "label": "Initialisation du scrape stable"})
        _run_source_slugs_sync(stable_slugs, progress_cb=progress_cb)
        if progress_cb:
            progress_cb({"phase": "export", "percent": 95, "label": "Export en cours"})
        return _export_sync(
            None,
            export_format,
            min_score,
            source_slugs=stable_slugs,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            date_from=date_from,
            date_to=date_to,
            name_contains=name_contains,
        )

    def _normalize_export_format(value: str) -> str:
        fmt = (value or "csv").strip().lower()
        if fmt not in {"csv", "json", "xlsx"}:
            raise HTTPException(status_code=400, detail="export_format must be csv, json, or xlsx")
        return fmt

    def _normalize_page(limit: int, offset: int, max_limit: int = 500) -> tuple[int, int]:
        safe_limit = max(1, min(int(limit), max_limit))
        safe_offset = max(0, int(offset))
        return safe_limit, safe_offset

    def _parse_iso_datetime(value: str | None, field_name: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid {field_name}, expected ISO datetime") from exc

    def _schedule_key(entry: dict) -> str:
        return f"{entry['source_slug']}|{entry['export_format']}|{entry['min_score']}"

    def _queue_scheduled_run_export(entry: dict, key: str) -> str | None:
        selected = entry["source_slug"] or None
        export_format = entry["export_format"]
        min_score = int(entry["min_score"])

        payload = {
            "source_slug": selected or "*",
            "format": export_format,
            "min_score": min_score,
        }

        if task_backend == "db_queue":
            return _queue_task("scheduled_run_export", payload)

        with schedule_lock:
            if key in schedule_running:
                return None
            schedule_running.add(key)

        def _scheduled_job(progress_cb):
            try:
                return _run_then_export_sync(selected, export_format, min_score, progress_cb=progress_cb)
            finally:
                with schedule_lock:
                    schedule_running.discard(key)

        return _queue_task("scheduled_run_export", payload, _scheduled_job)

    def _scheduler_loop() -> None:
        while not schedule_stop.is_set():
            try:
                entries = list_schedules(schedule_file)
                now = now_utc()
                active_keys: set[str] = set()
                for entry in entries:
                    key = _schedule_key(entry)
                    active_keys.add(key)
                    if not entry["enabled"]:
                        continue
                    interval = max(1, int(entry["interval_minutes"]))
                    due_at = schedule_next_due.get(key)
                    if due_at is None:
                        schedule_next_due[key] = now + timedelta(minutes=interval)
                        continue
                    if now >= due_at:
                        _queue_scheduled_run_export(entry, key)
                        schedule_next_due[key] = now + timedelta(minutes=interval)
                for key in list(schedule_next_due.keys()):
                    if key not in active_keys:
                        schedule_next_due.pop(key, None)
            except Exception as exc:
                logger.error("ui_scheduler_failed", error=str(exc), trace=traceback.format_exc())
            finally:
                time.sleep(15)

    def _collect_metrics() -> dict:
        last_24h = now_utc() - timedelta(hours=24)
        with Session(engine) as session:
            total_leads = session.scalar(select(func.count()).select_from(LeadORM)) or 0
            total_jobs = session.scalar(select(func.count()).select_from(ScrapeJobORM)) or 0
            total_errors = session.scalar(select(func.count()).select_from(ErrorLogORM)) or 0
            jobs_24h_rows = session.scalars(
                select(ScrapeJobORM).where(ScrapeJobORM.started_at >= last_24h).order_by(ScrapeJobORM.id.desc())
            ).all()
            jobs_24h = len(jobs_24h_rows)
            success_24h = len([j for j in jobs_24h_rows if j.status == "success"])
            failed_24h = len([j for j in jobs_24h_rows if j.status == "failed"])
            duration_samples = [
                (j.finished_at - j.started_at).total_seconds()
                for j in jobs_24h_rows
                if j.started_at is not None and j.finished_at is not None
            ]
            avg_duration_24h = round(sum(duration_samples) / len(duration_samples), 2) if duration_samples else 0.0

            if task_backend == "db_queue":
                counts = dict(
                    session.execute(
                        select(QueueTaskORM.status, func.count())
                        .group_by(QueueTaskORM.status)
                        .order_by(QueueTaskORM.status.asc())
                    ).all()
                )
                task_status = {
                    "queued": int(counts.get("queued", 0)),
                    "running": int(counts.get("running", 0)),
                    "success": int(counts.get("success", 0)),
                    # Keep failed as backward-compatible aggregate for dashboards.
                    "failed": int(counts.get("failed", 0)) + int(counts.get("dead", 0)),
                    "dead": int(counts.get("dead", 0)),
                }
            else:
                tasks = _memory_recent_tasks(200)
                task_status = {
                    "queued": len([t for t in tasks if t["status"] == "queued"]),
                    "running": len([t for t in tasks if t["status"] == "running"]),
                    "success": len([t for t in tasks if t["status"] == "success"]),
                    "failed": len([t for t in tasks if t["status"] == "failed"]),
                    "dead": len([t for t in tasks if t["status"] == "dead"]),
                }
        schedules = list_schedules(schedule_file)
        active_schedules = len([s for s in schedules if s["enabled"]])
        return {
            "total_leads": int(total_leads),
            "total_jobs": int(total_jobs),
            "total_errors": int(total_errors),
            "task_status": task_status,
            "task_backend": task_backend,
            "total_schedules": len(schedules),
            "active_schedules": active_schedules,
            "jobs_24h": jobs_24h,
            "jobs_24h_success": success_24h,
            "jobs_24h_failed": failed_24h,
            "jobs_24h_avg_duration_seconds": avg_duration_24h,
            "timestamp_utc": now_utc().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics/json")
    def metrics_json():
        return _collect_metrics()

    @app.get("/api/v1/monitoring/summary")
    def api_monitoring_summary(
        health_window_jobs: int | None = None,
        health_threshold: int | None = None,
    ):
        metrics = _collect_metrics()
        safe_window = max(1, int(health_window_jobs if health_window_jobs is not None else settings.source_health_window_jobs))
        threshold = max(
            0,
            int(health_threshold if health_threshold is not None else settings.source_health_auto_disable_failures),
        )
        with Session(engine) as session:
            source_health = compute_source_health(
                session,
                sources_dir="config/sources",
                window_jobs=safe_window,
                auto_disable_failures=threshold,
                apply_changes=False,
            )
        top_unhealthy = source_health["items"][:10]
        return {
            "metrics": metrics,
            "source_health": {
                "window_jobs": source_health["window_jobs"],
                "auto_disable_failures": source_health["auto_disable_failures"],
                "disabled_now": source_health["disabled_now"],
                "top_unhealthy": top_unhealthy,
            },
        }

    @app.get("/metrics/prometheus", response_class=PlainTextResponse)
    def metrics_prometheus():
        metrics = _collect_metrics()
        lines = [
            "# HELP winxtract_leads_total Total leads stored",
            "# TYPE winxtract_leads_total gauge",
            f"winxtract_leads_total {metrics['total_leads']}",
            "# HELP winxtract_jobs_total Total scrape jobs stored",
            "# TYPE winxtract_jobs_total gauge",
            f"winxtract_jobs_total {metrics['total_jobs']}",
            "# HELP winxtract_errors_total Total error logs stored",
            "# TYPE winxtract_errors_total gauge",
            f"winxtract_errors_total {metrics['total_errors']}",
            "# HELP winxtract_jobs_24h Total jobs started in the last 24h",
            "# TYPE winxtract_jobs_24h gauge",
            f"winxtract_jobs_24h {metrics['jobs_24h']}",
            "# HELP winxtract_jobs_24h_success Successful jobs in the last 24h",
            "# TYPE winxtract_jobs_24h_success gauge",
            f"winxtract_jobs_24h_success {metrics['jobs_24h_success']}",
            "# HELP winxtract_jobs_24h_failed Failed jobs in the last 24h",
            "# TYPE winxtract_jobs_24h_failed gauge",
            f"winxtract_jobs_24h_failed {metrics['jobs_24h_failed']}",
            "# HELP winxtract_jobs_24h_avg_duration_seconds Average job duration over last 24h",
            "# TYPE winxtract_jobs_24h_avg_duration_seconds gauge",
            f"winxtract_jobs_24h_avg_duration_seconds {metrics['jobs_24h_avg_duration_seconds']}",
            "# HELP winxtract_schedules_total Total schedules configured",
            "# TYPE winxtract_schedules_total gauge",
            f"winxtract_schedules_total {metrics['total_schedules']}",
            "# HELP winxtract_schedules_active Active schedules",
            "# TYPE winxtract_schedules_active gauge",
            f"winxtract_schedules_active {metrics['active_schedules']}",
            "# HELP winxtract_ui_tasks Number of UI tasks by status",
            "# TYPE winxtract_ui_tasks gauge",
            f"winxtract_ui_tasks{{status=\"queued\"}} {metrics['task_status']['queued']}",
            f"winxtract_ui_tasks{{status=\"running\"}} {metrics['task_status']['running']}",
            f"winxtract_ui_tasks{{status=\"success\"}} {metrics['task_status']['success']}",
            f"winxtract_ui_tasks{{status=\"failed\"}} {metrics['task_status']['failed']}",
            f"winxtract_ui_tasks{{status=\"dead\"}} {metrics['task_status']['dead']}",
            "# HELP winxtract_task_backend Current task backend (0=thread,1=db_queue)",
            "# TYPE winxtract_task_backend gauge",
            f"winxtract_task_backend {1 if metrics['task_backend'] == 'db_queue' else 0}",
        ]
        return "\n".join(lines) + "\n"

    @app.get("/api/v1/health")
    def api_health():
        return {"status": "ok"}

    @app.get("/api/v1/sources")
    def api_sources(enabled: bool | None = None):
        rows = list_source_entries("config/sources")
        if enabled is not None:
            rows = [row for row in rows if row["enabled"] == enabled]
        return {
            "count": len(rows),
            "items": [_source_to_dict(row) for row in rows],
        }

    @app.get("/api/v1/jobs")
    def api_jobs(
        source_slug: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        safe_limit, safe_offset = _normalize_page(limit, offset)
        with Session(engine) as session:
            stmt = select(ScrapeJobORM).order_by(ScrapeJobORM.id.desc())
            if source_slug:
                stmt = stmt.where(ScrapeJobORM.source_slug == source_slug)
            if status:
                stmt = stmt.where(ScrapeJobORM.status == status)
            total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = session.scalars(stmt.offset(safe_offset).limit(safe_limit)).all()
        return {
            "count": len(rows),
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "items": [_job_to_dict(row) for row in rows],
        }

    @app.get("/api/v1/leads")
    def api_leads(
        source_slug: str | None = None,
        min_score: int = 0,
        city: str | None = None,
        has_email: bool | None = None,
        has_phone: bool | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        name_contains: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        safe_limit, safe_offset = _normalize_page(limit, offset)
        parsed_from = _parse_iso_datetime(date_from, "date_from")
        parsed_to = _parse_iso_datetime(date_to, "date_to")
        with Session(engine) as session:
            stmt = select(LeadORM).where(LeadORM.score >= max(0, min(100, int(min_score))))
            if source_slug:
                stmt = stmt.where(LeadORM.source_slug == source_slug)
            if city:
                stmt = stmt.where(LeadORM.city == city)
            if has_email is True:
                stmt = stmt.where((LeadORM.emails.is_not(None)) & (LeadORM.emails != ""))
            elif has_email is False:
                stmt = stmt.where((LeadORM.emails.is_(None)) | (LeadORM.emails == ""))
            if has_phone is True:
                stmt = stmt.where((LeadORM.phones.is_not(None)) & (LeadORM.phones != ""))
            elif has_phone is False:
                stmt = stmt.where((LeadORM.phones.is_(None)) | (LeadORM.phones == ""))
            if parsed_from:
                stmt = stmt.where(LeadORM.scraped_at >= parsed_from)
            if parsed_to:
                stmt = stmt.where(LeadORM.scraped_at <= parsed_to)
            if name_contains:
                stmt = stmt.where(LeadORM.name.ilike(f"%{name_contains.strip()}%"))
            stmt = stmt.order_by(LeadORM.scraped_at.desc())
            total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = session.scalars(stmt.offset(safe_offset).limit(safe_limit)).all()
        return {
            "count": len(rows),
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "items": [_lead_to_dict(row) for row in rows],
        }

    @app.get("/api/v1/errors")
    def api_errors(
        source_slug: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        safe_limit, safe_offset = _normalize_page(limit, offset)
        with Session(engine) as session:
            stmt = select(ErrorLogORM).order_by(ErrorLogORM.id.desc())
            if source_slug:
                stmt = stmt.where(ErrorLogORM.source_slug == source_slug)
            total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = session.scalars(stmt.offset(safe_offset).limit(safe_limit)).all()
        return {
            "count": len(rows),
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "items": [_error_to_dict(row) for row in rows],
        }

    @app.get("/api/v1/tasks")
    def api_tasks(status: str | None = None, limit: int = 100):
        safe_limit = max(1, min(int(limit), 500))
        rows = _recent_tasks(safe_limit)
        if status:
            rows = [row for row in rows if row["status"] == status]
        return {
            "count": len(rows),
            "backend": task_backend,
            "items": [_task_to_dict(row) for row in rows],
        }

    @app.get("/api/v1/dead-letters")
    def api_dead_letters(
        status: str = "all",
        task_type: str = "",
        source_slug: str = "",
        message_contains: str = "",
        limit: int = 200,
    ):
        if task_backend != "db_queue":
            raise HTTPException(status_code=400, detail="dead letters are available only with db_queue backend")
        safe_status = _safe_dead_filter_status(status)
        safe_limit = max(1, min(int(limit), 500))
        rows = _filtered_dead_tasks(
            status=safe_status,
            task_type=task_type,
            source_slug=source_slug,
            message_contains=message_contains,
            limit=safe_limit,
        )
        return {
            "count": len(rows),
            "backend": task_backend,
            "filters": {
                "status": safe_status,
                "task_type": task_type.strip(),
                "source_slug": _safe_source_filter(source_slug),
                "message_contains": message_contains.strip(),
                "limit": safe_limit,
            },
            "items": [_task_to_dict(row) for row in rows],
        }

    @app.get("/api/v1/tasks/{task_id}")
    def api_task_detail(task_id: str):
        row = _task_by_id(task_id)
        if not row:
            raise HTTPException(status_code=404, detail="task not found")
        return _task_to_dict(row)

    @app.post("/api/v1/tasks/{task_id}/requeue")
    def api_task_requeue(task_id: str):
        if task_backend != "db_queue":
            raise HTTPException(status_code=400, detail="requeue is available only with db_queue backend")
        try:
            parsed = int(task_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid task_id") from exc
        replay = queue_store.requeue_task(parsed, allowed_statuses=("dead", "failed"))
        if replay is None:
            raise HTTPException(status_code=404, detail="task not requeueable")
        return {"task_id": str(replay.id), "status": "queued", "requeued_from": str(task_id)}

    @app.post("/api/v1/tasks/requeue-batch")
    def api_tasks_requeue_batch(payload: RequeueBatchRequest):
        if task_backend != "db_queue":
            raise HTTPException(status_code=400, detail="requeue is available only with db_queue backend")

        selected_ids = _parse_task_ids(payload.task_ids)
        if selected_ids:
            count, ids = _requeue_many(selected_ids)
            return {"status": "ok", "requeued_count": count, "task_ids": [str(i) for i in ids]}

        rows = _filtered_dead_tasks(
            status=_safe_dead_filter_status(payload.status),
            task_type=payload.task_type,
            source_slug=payload.source_slug,
            message_contains=payload.message_contains,
            limit=max(1, min(int(payload.limit), 500)),
        )
        count, ids = _requeue_many([int(row["id"]) for row in rows])
        return {"status": "ok", "requeued_count": count, "task_ids": [str(i) for i in ids]}

    @app.get("/api/v1/exports")
    def api_exports(limit: int = 50):
        safe_limit = max(1, min(int(limit), 500))
        rows = sorted(
            [
                {
                    "name": file.name,
                    "size": file.stat().st_size,
                    "mtime": datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc),
                    "download_path": f"/exports-files/{file.name}",
                }
                for file in exports_dir.glob("leads_*.*")
                if file.is_file()
            ],
            key=lambda x: x["mtime"],
            reverse=True,
        )[:safe_limit]
        return {"count": len(rows), "items": rows}

    @app.get("/api/v1/quality")
    def api_quality(source_slug: str | None = None):
        with Session(engine) as session:
            return compute_quality_report(session, source_slug=source_slug)

    @app.get("/api/v1/source-health")
    def api_source_health(
        window_jobs: int | None = None,
        auto_disable_failures: int | None = None,
        apply_changes: bool = False,
    ):
        safe_window = max(1, int(window_jobs if window_jobs is not None else settings.source_health_window_jobs))
        threshold = max(
            0,
            int(
                auto_disable_failures
                if auto_disable_failures is not None
                else settings.source_health_auto_disable_failures
            ),
        )
        with Session(engine) as session:
            return compute_source_health(
                session,
                sources_dir="config/sources",
                window_jobs=safe_window,
                auto_disable_failures=threshold,
                apply_changes=apply_changes,
            )

    @app.post("/api/v1/actions/run")
    def api_action_run(payload: RunActionRequest):
        selected = payload.source_slug.strip() if payload.source_slug else None
        task_id = _queue_task(
            "run",
            {"source_slug": selected or "*"},
            lambda progress_cb: _run_source_sync(selected, progress_cb=progress_cb),
        )
        return {"task_id": task_id, "status": "queued"}

    @app.post("/api/v1/actions/export")
    def api_action_export(payload: ExportActionRequest):
        selected = payload.source_slug.strip() if payload.source_slug else None
        export_format = _normalize_export_format(payload.export_format)
        min_score = max(0, min(100, int(payload.min_score)))
        parsed_from = _parse_iso_datetime(payload.date_from, "date_from")
        parsed_to = _parse_iso_datetime(payload.date_to, "date_to")
        task_id = _queue_task(
            "export",
            {
                "source_slug": selected or "*",
                "format": export_format,
                "min_score": min_score,
                "city": payload.city,
                "has_email": payload.has_email,
                "has_phone": payload.has_phone,
                "date_from": payload.date_from,
                "date_to": payload.date_to,
                "name_contains": payload.name_contains,
            },
            lambda progress_cb: _export_sync(
                selected,
                export_format,
                min_score,
                city=payload.city,
                has_email=payload.has_email,
                has_phone=payload.has_phone,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=payload.name_contains,
                progress_cb=progress_cb,
            ),
        )
        return {"task_id": task_id, "status": "queued"}

    @app.post("/api/v1/actions/run-export")
    def api_action_run_export(payload: ExportActionRequest):
        selected = payload.source_slug.strip() if payload.source_slug else None
        export_format = _normalize_export_format(payload.export_format)
        min_score = max(0, min(100, int(payload.min_score)))
        parsed_from = _parse_iso_datetime(payload.date_from, "date_from")
        parsed_to = _parse_iso_datetime(payload.date_to, "date_to")
        task_id = _queue_task(
            "run_export",
            {
                "source_slug": selected or "*",
                "format": export_format,
                "min_score": min_score,
                "city": payload.city,
                "has_email": payload.has_email,
                "has_phone": payload.has_phone,
                "date_from": payload.date_from,
                "date_to": payload.date_to,
                "name_contains": payload.name_contains,
            },
            lambda progress_cb: _run_then_export_sync(
                selected,
                export_format,
                min_score,
                city=payload.city,
                has_email=payload.has_email,
                has_phone=payload.has_phone,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=payload.name_contains,
                progress_cb=progress_cb,
            ),
        )
        return {"task_id": task_id, "status": "queued"}

    @app.post("/api/v1/actions/run-export-stable")
    def api_action_run_export_stable(payload: ExportActionRequest):
        export_format = _normalize_export_format(payload.export_format)
        min_score = max(0, min(100, int(payload.min_score)))
        parsed_from = _parse_iso_datetime(payload.date_from, "date_from")
        parsed_to = _parse_iso_datetime(payload.date_to, "date_to")
        task_id = _queue_task(
            "run_export_stable",
            {
                "pack": "stable",
                "format": export_format,
                "min_score": min_score,
                "city": payload.city,
                "has_email": payload.has_email,
                "has_phone": payload.has_phone,
                "date_from": payload.date_from,
                "date_to": payload.date_to,
                "name_contains": payload.name_contains,
            },
            lambda progress_cb: _run_stable_then_export_sync(
                export_format,
                min_score,
                city=payload.city,
                has_email=payload.has_email,
                has_phone=payload.has_phone,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=payload.name_contains,
                progress_cb=progress_cb,
            ),
        )
        return {"task_id": task_id, "status": "queued"}

    @app.post("/api/v1/actions/run-export-all")
    def api_action_run_export_all(payload: ExportActionRequest):
        export_format = _normalize_export_format(payload.export_format)
        min_score = max(0, min(100, int(payload.min_score)))
        parsed_from = _parse_iso_datetime(payload.date_from, "date_from")
        parsed_to = _parse_iso_datetime(payload.date_to, "date_to")
        task_id = _queue_task(
            "run_export_all",
            {
                "scope": "all_active",
                "format": export_format,
                "min_score": min_score,
                "city": payload.city,
                "has_email": payload.has_email,
                "has_phone": payload.has_phone,
                "date_from": payload.date_from,
                "date_to": payload.date_to,
                "name_contains": payload.name_contains,
            },
            lambda progress_cb: _run_then_export_sync(
                None,
                export_format,
                min_score,
                city=payload.city,
                has_email=payload.has_email,
                has_phone=payload.has_phone,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=payload.name_contains,
                progress_cb=progress_cb,
            ),
        )
        return {"task_id": task_id, "status": "queued"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, msg: str | None = None):
        snapshot = _dashboard_snapshot()
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "msg": msg,
                "active_sources_count": snapshot["active_sources_count"],
                "stable_sources_count": snapshot["stable_sources_count"],
                "active_schedules_count": snapshot["active_schedules_count"],
                "total_leads": snapshot["total_leads"],
                "total_jobs": snapshot["total_jobs"],
                "total_errors": snapshot["total_errors"],
                "recent_jobs": snapshot["recent_jobs"],
                "source_labels": snapshot["source_labels"],
                "task_backend": snapshot["task_backend"],
            },
        )

    @app.get("/operations", response_class=HTMLResponse)
    def operations_page(request: Request, msg: str | None = None):
        snapshot = _dashboard_snapshot()
        return templates.TemplateResponse(
            request,
            "operations.html",
            {
                "msg": msg,
                "sources": snapshot["sources"],
                "source_entries": snapshot["source_entries"],
                "ui_tasks": _recent_tasks(40),
                "task_backend": snapshot["task_backend"],
            },
        )

    @app.get("/exports", response_class=HTMLResponse)
    def exports_page(request: Request, msg: str | None = None):
        snapshot = _dashboard_snapshot()
        return templates.TemplateResponse(
            request,
            "exports.html",
            {
                "msg": msg,
                "sources": snapshot["sources"],
                "export_files": _list_export_files(limit=50),
                "total_leads": snapshot["total_leads"],
            },
        )

    @app.get("/sources", response_class=HTMLResponse)
    def sources_page(request: Request, msg: str | None = None):
        snapshot = _dashboard_snapshot()
        return templates.TemplateResponse(
            request,
            "sources.html",
            {
                "msg": msg,
                "source_entries": snapshot["source_entries"],
                "active_sources_count": snapshot["active_sources_count"],
                "stable_sources_count": snapshot["stable_sources_count"],
            },
        )

    @app.get("/onboarding", response_class=HTMLResponse)
    def onboarding_page(request: Request, msg: str | None = None):
        snapshot = _dashboard_snapshot()
        enabled_sources = snapshot["sources"]
        privacy_ready_sources = [
            row
            for row in enabled_sources
            if (row.get("privacy_mode") or "").strip().lower() in {"b2c_conforme", "b2c_etendu"}
        ]
        privacy_ready = bool(enabled_sources) and len(privacy_ready_sources) == len(enabled_sources)
        latest_export = _list_export_files(limit=1)
        last_export = latest_export[0] if latest_export else None
        with Session(engine) as session:
            last_success_job = session.scalar(
                select(ScrapeJobORM)
                .where(ScrapeJobORM.status.in_(["success", "completed"]))
                .order_by(ScrapeJobORM.id.desc())
                .limit(1)
            )
        blockers: list[str] = []
        if not enabled_sources:
            blockers.append("Aucune source active. Active au moins une source avant execution.")
        if not privacy_ready:
            blockers.append("Toutes les sources actives ne sont pas encore sur un profil privacy B2C.")
        if not last_export:
            blockers.append("Aucun export detecte pour l'instant.")
        return templates.TemplateResponse(
            request,
            "onboarding.html",
            {
                "msg": msg,
                "sources": snapshot["sources"],
                "source_entries": snapshot["source_entries"],
                "active_sources_count": snapshot["active_sources_count"],
                "privacy_ready_count": len(privacy_ready_sources),
                "privacy_ready": privacy_ready,
                "last_export": last_export,
                "last_success_job": last_success_job,
                "blockers": blockers,
            },
        )

    @app.post("/run")
    def run_job(
        source_slug: str = Form(""),
        next_page: str = Form(""),
    ):
        selected = source_slug.strip() or None
        task_id = _queue_task(
            "run",
            {"source_slug": selected or "*"},
            lambda progress_cb: _run_source_sync(selected, progress_cb=progress_cb),
        )
        target = _safe_next_page(next_page, "/operations")
        return _redirect_with_msg(target, f"Run queued (task {task_id})")

    @app.post("/sources/toggle")
    def toggle_source(
        source_slug: str = Form(...),
        enabled: str = Form(...),
        next_page: str = Form(""),
    ):
        target = _safe_next_page(next_page, "/sources")
        target_state = enabled.lower() == "true"
        found = set_source_enabled("config/sources", source_slug, target_state)
        if not found:
            return _redirect_with_msg(target, "Source not found")
        status = "enabled" if target_state else "disabled"
        return _redirect_with_msg(target, f"Source {source_slug} {status}")

    @app.post("/sources/privacy-profile")
    def apply_privacy_profile(
        source_slug: str = Form("*"),
        privacy_profile: str = Form("b2c_conforme"),
        next_page: str = Form(""),
    ):
        redirect_to = _safe_next_page(next_page, "/sources")
        target_slug = source_slug.strip() or "*"
        profile = privacy_profile.strip().lower()
        try:
            updated = set_source_privacy_profile("config/sources", target_slug, profile)
        except ValueError:
            return _redirect_with_msg(redirect_to, "Invalid privacy profile")
        return _redirect_with_msg(redirect_to, f"Privacy profile {profile} applied ({updated} source(s))")

    @app.post("/export")
    def export_job(
        export_format: str = Form("csv"),
        min_score: int = Form(0),
        source_slug: str = Form(""),
        city: str = Form(""),
        has_email: str = Form(""),
        has_phone: str = Form(""),
        date_from: str = Form(""),
        date_to: str = Form(""),
        name_contains: str = Form(""),
        next_page: str = Form(""),
    ):
        selected = source_slug.strip() or None
        redirect_to = _safe_next_page(next_page, "/exports")
        normalized_format = _normalize_export_format(export_format)
        city_filter = city.strip() or None
        name_filter = name_contains.strip() or None
        has_email_filter = None if has_email.strip() == "" else (has_email.strip().lower() == "true")
        has_phone_filter = None if has_phone.strip() == "" else (has_phone.strip().lower() == "true")
        parsed_from = _parse_iso_datetime(date_from.strip() or None, "date_from")
        parsed_to = _parse_iso_datetime(date_to.strip() or None, "date_to")
        task_id = _queue_task(
            "export",
            {
                "source_slug": selected or "*",
                "format": normalized_format,
                "min_score": min_score,
                "city": city_filter,
                "has_email": has_email_filter,
                "has_phone": has_phone_filter,
                "date_from": date_from or None,
                "date_to": date_to or None,
                "name_contains": name_filter,
            },
            lambda progress_cb: _export_sync(
                selected,
                normalized_format,
                min_score,
                city=city_filter,
                has_email=has_email_filter,
                has_phone=has_phone_filter,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=name_filter,
                progress_cb=progress_cb,
            ),
        )
        return _redirect_with_msg(redirect_to, f"Export queued (task {task_id})")

    @app.post("/run-export")
    def run_and_export_job(
        source_slug: str = Form(""),
        export_format: str = Form("csv"),
        min_score: int = Form(0),
        city: str = Form(""),
        has_email: str = Form(""),
        has_phone: str = Form(""),
        date_from: str = Form(""),
        date_to: str = Form(""),
        name_contains: str = Form(""),
        next_page: str = Form(""),
    ):
        selected = source_slug.strip() or None
        redirect_to = _safe_next_page(next_page, "/operations")
        normalized_format = _normalize_export_format(export_format)
        city_filter = city.strip() or None
        name_filter = name_contains.strip() or None
        has_email_filter = None if has_email.strip() == "" else (has_email.strip().lower() == "true")
        has_phone_filter = None if has_phone.strip() == "" else (has_phone.strip().lower() == "true")
        parsed_from = _parse_iso_datetime(date_from.strip() or None, "date_from")
        parsed_to = _parse_iso_datetime(date_to.strip() or None, "date_to")
        task_id = _queue_task(
            "run_export",
            {
                "source_slug": selected or "*",
                "format": normalized_format,
                "min_score": min_score,
                "city": city_filter,
                "has_email": has_email_filter,
                "has_phone": has_phone_filter,
                "date_from": date_from or None,
                "date_to": date_to or None,
                "name_contains": name_filter,
            },
            lambda progress_cb: _run_then_export_sync(
                selected,
                normalized_format,
                min_score,
                city=city_filter,
                has_email=has_email_filter,
                has_phone=has_phone_filter,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=name_filter,
                progress_cb=progress_cb,
            ),
        )
        return _redirect_with_msg(redirect_to, f"Run+Export queued (task {task_id})")

    @app.post("/run-export-stable")
    def run_and_export_stable_job(
        export_format: str = Form("csv"),
        min_score: int = Form(0),
        city: str = Form(""),
        has_email: str = Form(""),
        has_phone: str = Form(""),
        date_from: str = Form(""),
        date_to: str = Form(""),
        name_contains: str = Form(""),
        next_page: str = Form(""),
    ):
        redirect_to = _safe_next_page(next_page, "/operations")
        normalized_format = _normalize_export_format(export_format)
        city_filter = city.strip() or None
        name_filter = name_contains.strip() or None
        has_email_filter = None if has_email.strip() == "" else (has_email.strip().lower() == "true")
        has_phone_filter = None if has_phone.strip() == "" else (has_phone.strip().lower() == "true")
        parsed_from = _parse_iso_datetime(date_from.strip() or None, "date_from")
        parsed_to = _parse_iso_datetime(date_to.strip() or None, "date_to")
        task_id = _queue_task(
            "run_export_stable",
            {
                "pack": "stable",
                "format": normalized_format,
                "min_score": min_score,
                "city": city_filter,
                "has_email": has_email_filter,
                "has_phone": has_phone_filter,
                "date_from": date_from or None,
                "date_to": date_to or None,
                "name_contains": name_filter,
            },
            lambda progress_cb: _run_stable_then_export_sync(
                normalized_format,
                min_score,
                city=city_filter,
                has_email=has_email_filter,
                has_phone=has_phone_filter,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=name_filter,
                progress_cb=progress_cb,
            ),
        )
        return _redirect_with_msg(redirect_to, f"Stable Run+Export queued (task {task_id})")

    @app.post("/run-export-all")
    def run_and_export_all_job(
        export_format: str = Form("csv"),
        min_score: int = Form(0),
        city: str = Form(""),
        has_email: str = Form(""),
        has_phone: str = Form(""),
        date_from: str = Form(""),
        date_to: str = Form(""),
        name_contains: str = Form(""),
        next_page: str = Form(""),
    ):
        redirect_to = _safe_next_page(next_page, "/operations")
        normalized_format = _normalize_export_format(export_format)
        city_filter = city.strip() or None
        name_filter = name_contains.strip() or None
        has_email_filter = None if has_email.strip() == "" else (has_email.strip().lower() == "true")
        has_phone_filter = None if has_phone.strip() == "" else (has_phone.strip().lower() == "true")
        parsed_from = _parse_iso_datetime(date_from.strip() or None, "date_from")
        parsed_to = _parse_iso_datetime(date_to.strip() or None, "date_to")
        task_id = _queue_task(
            "run_export_all",
            {
                "scope": "all_active",
                "format": normalized_format,
                "min_score": min_score,
                "city": city_filter,
                "has_email": has_email_filter,
                "has_phone": has_phone_filter,
                "date_from": date_from or None,
                "date_to": date_to or None,
                "name_contains": name_filter,
            },
            lambda progress_cb: _run_then_export_sync(
                None,
                normalized_format,
                min_score,
                city=city_filter,
                has_email=has_email_filter,
                has_phone=has_phone_filter,
                date_from=parsed_from,
                date_to=parsed_to,
                name_contains=name_filter,
                progress_cb=progress_cb,
            ),
        )
        return _redirect_with_msg(redirect_to, f"France entiere queued (task {task_id})")

    @app.get("/scheduler", response_class=HTMLResponse)
    def scheduler_page(request: Request):
        source_entries = list_source_entries("config/sources")
        source_labels = _source_label_map(source_entries)
        schedules = list_schedules(schedule_file)
        return templates.TemplateResponse(
            request,
            "scheduler.html",
            {
                "source_entries": source_entries,
                "source_labels": source_labels,
                "schedules": schedules,
            },
        )

    @app.post("/scheduler/save")
    def scheduler_save(
        source_slug: str = Form(...),
        interval_minutes: int = Form(60),
        export_format: str = Form("csv"),
        min_score: int = Form(0),
        enabled: str = Form("true"),
    ):
        slug = source_slug.strip()
        if not slug:
            return RedirectResponse(url=f"/scheduler?msg={quote_plus('source_slug required')}", status_code=303)
        upsert_schedule(
            schedule_file,
            source_slug=slug,
            enabled=(enabled.lower() == "true"),
            interval_minutes=interval_minutes,
            export_format=export_format,
            min_score=min_score,
        )
        return RedirectResponse(url=f"/scheduler?msg={quote_plus('schedule saved')}", status_code=303)

    @app.post("/scheduler/toggle")
    def scheduler_toggle(
        source_slug: str = Form(...),
        enabled: str = Form(...),
    ):
        found = set_schedule_enabled(schedule_file, source_slug, enabled.lower() == "true")
        if not found:
            return RedirectResponse(url=f"/scheduler?msg={quote_plus('schedule not found')}", status_code=303)
        return RedirectResponse(url=f"/scheduler?msg={quote_plus('schedule updated')}", status_code=303)

    @app.post("/scheduler/trigger")
    def scheduler_trigger(source_slug: str = Form(...)):
        schedules = list_schedules(schedule_file)
        target = None
        for entry in schedules:
            if entry["source_slug"] == source_slug:
                target = entry
                break
        if target is None:
            return RedirectResponse(url=f"/scheduler?msg={quote_plus('schedule not found')}", status_code=303)
        task_id = _queue_task(
            "scheduled_run_export_manual",
            {
                "source_slug": target["source_slug"],
                "format": target["export_format"],
                "min_score": target["min_score"],
            },
            lambda progress_cb: _run_then_export_sync(
                target["source_slug"],
                target["export_format"],
                target["min_score"],
                progress_cb=progress_cb,
            ),
        )
        return RedirectResponse(
            url=f"/scheduler?msg={quote_plus(f'manual trigger queued ({task_id})')}",
            status_code=303,
        )

    @app.get("/errors", response_class=HTMLResponse)
    def errors_page(request: Request):
        with Session(engine) as session:
            error_rows = (
                session.scalars(select(ErrorLogORM).order_by(ErrorLogORM.id.desc()).limit(200)).all()
            )
        return templates.TemplateResponse(
            request,
            "errors.html",
            {
                "error_rows": error_rows,
            },
        )

    @app.get("/leads", response_class=HTMLResponse)
    def leads_page(
        request: Request,
        source_slug: str = "",
        min_score: int = 0,
        limit: int = 100,
    ):
        safe_limit = max(1, min(limit, 500))
        source_entries = list_source_entries("config/sources")
        with Session(engine) as session:
            stmt = select(LeadORM).where(LeadORM.score >= min_score)
            if source_slug:
                stmt = stmt.where(LeadORM.source_slug == source_slug)
            leads = session.scalars(stmt.order_by(LeadORM.scraped_at.desc()).limit(safe_limit)).all()
        return templates.TemplateResponse(
            request,
            "leads.html",
            {
                "leads": leads,
                "source_slug": source_slug,
                "source_entries": source_entries,
                "min_score": min_score,
                "limit": safe_limit,
            },
        )

    @app.get("/quality", response_class=HTMLResponse)
    def quality_page(request: Request, source_slug: str = ""):
        selected = source_slug.strip() or None
        source_entries = list_source_entries("config/sources")
        source_labels = _source_label_map(source_entries)
        with Session(engine) as session:
            report = compute_quality_report(session, source_slug=selected)
        return templates.TemplateResponse(
            request,
            "quality.html",
            {
                "source_slug": selected or "",
                "source_entries": source_entries,
                "source_labels": source_labels,
                "report": report,
            },
        )

    @app.get("/source-health", response_class=HTMLResponse)
    def source_health_page(
        request: Request,
        window_jobs: int = 10,
        auto_disable_failures: int = 0,
        msg: str | None = None,
    ):
        safe_window = max(1, min(int(window_jobs), 200))
        threshold = max(0, min(int(auto_disable_failures), 100))
        with Session(engine) as session:
            report = compute_source_health(
                session,
                sources_dir="config/sources",
                window_jobs=safe_window,
                auto_disable_failures=threshold,
                apply_changes=False,
            )
        return templates.TemplateResponse(
            request,
            "source_health.html",
            {
                "msg": msg,
                "report": report,
            },
        )

    @app.post("/source-health/auto-disable")
    def source_health_auto_disable(
        window_jobs: int = Form(10),
        auto_disable_failures: int = Form(3),
    ):
        safe_window = max(1, min(int(window_jobs), 200))
        threshold = max(1, min(int(auto_disable_failures), 100))
        with Session(engine) as session:
            report = compute_source_health(
                session,
                sources_dir="config/sources",
                window_jobs=safe_window,
                auto_disable_failures=threshold,
                apply_changes=True,
            )
        msg = quote_plus(f"Disabled now: {report['disabled_now']}")
        return RedirectResponse(
            url=f"/source-health?window_jobs={safe_window}&auto_disable_failures={threshold}&msg={msg}",
            status_code=303,
        )

    @app.get("/tasks", response_class=HTMLResponse)
    def tasks_page(request: Request, msg: str | None = None):
        return templates.TemplateResponse(
            request,
            "tasks.html",
            {
                "msg": msg,
                "ui_tasks": _recent_tasks(200),
                "task_backend": task_backend,
            },
        )

    @app.get("/dead-letters", response_class=HTMLResponse)
    def dead_letters_page(
        request: Request,
        msg: str | None = None,
        status: str = "all",
        task_type: str = "",
        source_slug: str = "",
        message_contains: str = "",
        limit: int = 200,
    ):
        safe_status = _safe_dead_filter_status(status)
        safe_limit = max(1, min(int(limit), 500))
        dead_tasks = _filtered_dead_tasks(
            status=safe_status,
            task_type=task_type,
            source_slug=source_slug,
            message_contains=message_contains,
            limit=safe_limit,
        )
        return templates.TemplateResponse(
            request,
            "dead_letters.html",
            {
                "msg": msg,
                "task_backend": task_backend,
                "dead_tasks": dead_tasks,
                "filters": {
                    "status": safe_status,
                    "task_type": task_type.strip(),
                    "source_slug": _safe_source_filter(source_slug),
                    "message_contains": message_contains.strip(),
                    "limit": safe_limit,
                },
            },
        )

    @app.post("/tasks/requeue")
    def tasks_requeue(
        task_id: str = Form(...),
        next_page: str = Form(""),
    ):
        target = _safe_next_page(next_page, "/dead-letters")
        if task_backend != "db_queue":
            return _redirect_with_msg(target, "Requeue disponible seulement en backend db_queue")
        try:
            parsed = int(task_id)
        except Exception:
            return _redirect_with_msg(target, "task_id invalide")
        replay = queue_store.requeue_task(parsed, allowed_statuses=("dead", "failed"))
        if replay is None:
            return _redirect_with_msg(target, "Tache non requeueable")
        return _redirect_with_msg(target, f"Tache relancee ({replay.id})")

    @app.post("/tasks/requeue-batch")
    def tasks_requeue_batch(
        status: str = Form("all"),
        task_type: str = Form(""),
        source_slug: str = Form(""),
        message_contains: str = Form(""),
        limit: int = Form(200),
        next_page: str = Form(""),
    ):
        target = _safe_next_page(next_page, "/dead-letters")
        if task_backend != "db_queue":
            return _redirect_with_msg(target, "Requeue disponible seulement en backend db_queue")

        rows = _filtered_dead_tasks(
            status=_safe_dead_filter_status(status),
            task_type=task_type,
            source_slug=source_slug,
            message_contains=message_contains,
            limit=max(1, min(int(limit), 500)),
        )
        count, _ = _requeue_many([int(row["id"]) for row in rows])
        return _redirect_with_msg(target, f"Taches relancees: {count}")

    return app

