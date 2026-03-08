import asyncio
import time
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from winxtract.core.browser_pool import BrowserPool
from winxtract.core.logging import get_logger
from winxtract.core.models import ScrapeStats, SourceConfig
from winxtract.core.pipeline import Pipeline
from winxtract.core.settings import Settings
from winxtract.scrapers.base import ScrapeContext
from winxtract.scrapers.registry import get_scraper
from winxtract.storage.repo import Repository

# Ensure scraper plugins are registered at import time.
import winxtract.scrapers.generic_css  # noqa: F401
import winxtract.scrapers.google_maps  # noqa: F401
import winxtract.scrapers.annuaire_118000  # noqa: F401
import winxtract.scrapers.data_gouv_dataset  # noqa: F401
import winxtract.scrapers.open_data_json  # noqa: F401
import winxtract.scrapers.pages_blanches  # noqa: F401
import winxtract.scrapers.pages_jaunes  # noqa: F401
import winxtract.scrapers.recherche_entreprises_api  # noqa: F401


class JobRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger("job_runner")

    async def run_sources(
        self,
        source_configs: Iterable[SourceConfig],
        session_factory: Callable[[], Session],
        on_progress: Callable[[dict], None] | None = None,
    ) -> dict[str, ScrapeStats]:
        source_list = list(source_configs)
        semaphore = asyncio.Semaphore(self.settings.max_source_concurrency)
        results: dict[str, ScrapeStats] = {}
        source_stats: dict[str, ScrapeStats] = {}
        source_status: dict[str, str] = {}

        def _emit_progress() -> None:
            if on_progress is None:
                return
            total_sources = len(source_list)
            completed_sources = sum(
                1 for slug in source_list if source_status.get(slug.slug) in {"success", "failed"}
            )
            running_sources = [slug.slug for slug in source_list if source_status.get(slug.slug) == "running"]
            pages = sum(stat.pages_scraped for stat in source_stats.values())
            leads = sum(stat.leads_extracted for stat in source_stats.values())
            errors = sum(stat.errors for stat in source_stats.values())
            duration = sum(stat.duration_seconds for stat in source_stats.values())
            pct = 100 if total_sources == 0 else int((completed_sources / total_sources) * 100)
            if running_sources and completed_sources < total_sources:
                pct = max(5, pct)
            on_progress(
                {
                    "phase": "scrape",
                    "sources_total": total_sources,
                    "sources_done": completed_sources,
                    "sources_running": running_sources,
                    "pages_scraped": pages,
                    "leads_extracted": leads,
                    "errors": errors,
                    "duration_seconds": round(duration, 2),
                    "percent": pct,
                }
            )

        for source in source_list:
            source_stats[source.slug] = ScrapeStats()
            source_status[source.slug] = "queued"
        _emit_progress()

        async def _one(source: SourceConfig):
            async with semaphore:
                source_status[source.slug] = "running"
                _emit_progress()
                stats = await self.run_single_source(
                    source,
                    session_factory,
                    on_progress=lambda payload: (
                        source_stats.__setitem__(
                            source.slug,
                            ScrapeStats(
                                pages_scraped=int(payload.get("pages_scraped", 0)),
                                leads_extracted=int(payload.get("leads_extracted", 0)),
                                errors=int(payload.get("errors", 0)),
                                duration_seconds=float(payload.get("duration_seconds", 0.0)),
                            ),
                        ),
                        source_status.__setitem__(source.slug, str(payload.get("status", "running"))),
                        _emit_progress(),
                    ),
                )
                results[source.slug] = stats
                source_stats[source.slug] = stats
                if source_status.get(source.slug) not in {"success", "failed"}:
                    source_status[source.slug] = "success"
                _emit_progress()

        await asyncio.gather(*[_one(source) for source in source_list])
        return results

    async def run_single_source(
        self,
        source: SourceConfig,
        session_factory: Callable[[], Session],
        on_progress: Callable[[dict], None] | None = None,
    ) -> ScrapeStats:
        with session_factory() as session:
            repo = Repository(session)
            repo.upsert_source(source.slug, source.scraper, source.enabled)
            job = repo.create_job(source.slug)

            stats = ScrapeStats()
            pipeline_params = dict(source.params)
            if "privacy_mode" not in pipeline_params and self.settings.privacy_mode.strip().lower() != "none":
                pipeline_params["privacy_mode"] = self.settings.privacy_mode
            pipeline = Pipeline(source_params=pipeline_params)
            start = time.perf_counter()

            pool = BrowserPool(
                headless=self.settings.headless,
                max_pages=self.settings.max_pages,
                timeout_ms=self.settings.default_timeout_ms,
                min_domain_delay=self.settings.min_domain_delay,
                max_retries=self.settings.max_retries,
                backoff_min=self.settings.backoff_min,
                backoff_max=self.settings.backoff_max,
                proxy_url=self.settings.proxy_url,
            )
            scraper_cls = get_scraper(source.scraper)
            scraper = scraper_cls()

            await pool.start()
            last_emit = time.perf_counter()
            heartbeat_task: asyncio.Task | None = None
            if on_progress:
                async def _heartbeat() -> None:
                    while True:
                        await asyncio.sleep(2)
                        on_progress(
                            {
                                "source_slug": source.slug,
                                "status": "running",
                                "pages_scraped": stats.pages_scraped,
                                "leads_extracted": stats.leads_extracted,
                                "errors": stats.errors,
                                "duration_seconds": round(time.perf_counter() - start, 2),
                            }
                        )

                heartbeat_task = asyncio.create_task(_heartbeat())
            try:
                ctx = ScrapeContext(source=source, browser_pool=pool, logger=self.logger)
                async for raw in scraper.scrape(ctx):
                    stats.pages_scraped += 1
                    try:
                        lead = pipeline.process_record(raw)
                        if lead is None:
                            continue
                        if repo.add_or_update_lead(lead):
                            stats.leads_extracted += 1
                    except Exception as exc:
                        stats.errors += 1
                        repo.log_error(source.slug, raw.page_url, exc)
                    now = time.perf_counter()
                    if on_progress and (stats.pages_scraped % 25 == 0 or now - last_emit >= 2.0):
                        on_progress(
                            {
                                "source_slug": source.slug,
                                "status": "running",
                                "pages_scraped": stats.pages_scraped,
                                "leads_extracted": stats.leads_extracted,
                                "errors": stats.errors,
                                "duration_seconds": round(now - start, 2),
                            }
                        )
                        last_emit = now
                status = "success"
            except Exception as exc:
                stats.errors += 1
                repo.log_error(source.slug, None, exc)
                status = "failed"
            finally:
                if heartbeat_task:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                await pool.stop()
                stats.duration_seconds = round(time.perf_counter() - start, 2)
                repo.finish_job(
                    job.id,
                    status=status,
                    pages=stats.pages_scraped,
                    leads=stats.leads_extracted,
                    errors=stats.errors,
                )
                if on_progress:
                    on_progress(
                        {
                            "source_slug": source.slug,
                            "status": status,
                            "pages_scraped": stats.pages_scraped,
                            "leads_extracted": stats.leads_extracted,
                            "errors": stats.errors,
                            "duration_seconds": stats.duration_seconds,
                        }
                    )
                self.logger.info(
                    "source_done",
                    source_slug=source.slug,
                    status=status,
                    pages_scraped=stats.pages_scraped,
                    leads_extracted=stats.leads_extracted,
                    errors=stats.errors,
                    duration_seconds=stats.duration_seconds,
                )

        return stats
