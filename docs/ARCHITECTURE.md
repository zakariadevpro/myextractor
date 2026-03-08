# WinXtract Architecture

## 1. Global architecture

Recommended stack:
- Python + Playwright for dynamic pages
- Typer CLI for MVP operations
- SQLite for local MVP, PostgreSQL for production scale
- Async orchestration with asyncio for scrapers
- Persistent queue worker in DB (`queue_tasks`) for throughput and decoupling UI/worker

Directory layout:
- `winxtract/scrapers`: source plugins
- `winxtract/core`: browser infra, rate limiting, retry, pipeline logic
- `winxtract/parsers`: extraction and normalization
- `winxtract/storage`: DB models, repository, exporters
- `winxtract/orchestrator`: job execution and concurrency
- `config/sources`: source definitions in YAML
- `config/source_catalog.yaml`: catalogue stable/candidate
- `ops/`: deployment and monitoring assets
- `docs`: architecture and implementation plan

## 2. Modular scraping system

- `BaseScraper` defines plugin contract
- Plugin registry allows adding new source with one class + one YAML file
- Included plugins:
  - `annuaire_118000_public`
  - `pages_blanches_public` (bootstrap)
  - `google_maps_public`
  - `pages_jaunes_public`
  - `generic_css`
  - `open_data_json`
  - `data_gouv_dataset`
- Generic plugin supports `css:` and `xpath:` selectors
- Pagination strategies: `click` and `rel_next`
- Pagination supported by optional `next_page` selector
- Robust errors captured per source and per record

## 3. Browser infrastructure

- Playwright Chromium in headless mode
- BrowserPool with max concurrent pages
- User-Agent rotation per page context
- Domain rate-limiter
- Retry/backoff hooks ready (`core/retries.py`)
- Timeout defaults from settings
- Robots.txt checks configurable by source

## 4. Data pipeline

Flow:
`scrape -> parse -> clean -> normalize -> score -> store`

Implemented:
- Email extraction with regex + syntax validation
- Phone extraction + E.164 normalization (`phonenumbers`)
- Text cleanup and canonicalization
- Dedup by email first, fallback `name+city` fingerprint
- Rule-based scoring (0-100)
- `particulier_conforme` mode (filtrage + redaction auto des champs sensibles)

## 5. Database model

Tables:
- `sources`
- `scrape_jobs`
- `leads`
- `error_logs`
- `queue_tasks`

Recommended indexes:
- `leads(fingerprint)` unique
- `leads(score, scraped_at)`
- `leads(source_slug, city)`
- `scrape_jobs(source_slug, status, started_at)`
- `error_logs(source_slug, created_at)`
- `queue_tasks(status, available_at, created_at)`

## 6. Export

Formats:
- CSV
- JSON
- XLSX

Filters:
- `min_score`
- `source_slug`
- `city`
- `has_email`
- `has_phone`
- `date_from` / `date_to`
- `name_contains`

## 7. Logging and monitoring

Structured logs (JSON):
- pages scraped
- leads extracted
- errors count
- source duration
- JSON metrics endpoint: `/metrics/json`
- Prometheus metrics endpoint: `/metrics/prometheus`
- Monitoring summary endpoint: `/api/v1/monitoring/summary`
- Dead-letter inspection endpoint: `/api/v1/dead-letters`
- Dead-letter replay endpoint: `/api/v1/tasks/requeue-batch`
- Source health endpoint: `/api/v1/source-health`
- Source health UI page: `/source-health`
- External control API: `/api/v1/*` (sources/jobs/leads/errors/tasks/actions/quality)
- Quality dashboard endpoint: `/quality`
- API token auth via `WINXTRACT_API_TOKEN`
- API rate limit via `WINXTRACT_API_RATE_LIMIT_PER_MINUTE`

Can be sent to ELK/Loki/Datadog later without changing domain code.

## 8. Scalability path (1k -> 100k leads/day)

Phase A (1k-10k/day):
- Single machine
- Async Playwright pool (4-10 pages)
- SQLite acceptable

Phase B (10k-40k/day):
- PostgreSQL
- DB queue backend (`WINXTRACT_TASK_BACKEND=db_queue`)
- Multiple `queue-worker` processes
- Separate scheduler from workers
- Per-domain concurrency caps

Phase C (40k-100k/day):
- Multiple worker nodes
- PostgreSQL tuning + partitioning by date
- Source-specific throttling profiles
- Centralized metrics and alerting
- Dead-letter queue for repeated failures (`queue_tasks.status=dead`)

Expected technical limits:
- Selector fragility on dynamic UIs
- Bot detection and legal boundaries
- Browser memory pressure
- DB write contention if dedupe is not indexed
