# WinXtract Implementation Plan

## Target
Build an independent, modular, MVP-ready scraping engine for public B2C data.

## Phase 1: MVP foundation (Day 1-2)
1. Setup project, dependencies, and CLI
2. Implement DB schema (SQLite) and migrations baseline
3. Build `BaseScraper`, plugin registry, and `generic_css`
4. Add browser pool, rate limiting, timeout, robots policy
5. Implement pipeline parse/clean/normalize/score/store
6. Add exports CSV/JSON/XLSX

Deliverable:
- Run one source end-to-end and export leads

## Phase 2: Source onboarding (Day 3-5)
1. Integrate Pages Jaunes public source
2. Integrate Google Maps public source
3. Add source YAML configs and selector tests
4. Add error taxonomy and retry rules by error type

Deliverable:
- At least 3 sources runnable via CLI

## Phase 3: Reliability (Week 2)
1. Add integration tests with saved HTML fixtures
2. Add idempotent job re-run behavior
3. Add metrics counters and execution summary
4. Add data quality checks (email/phone ratio, duplicate ratio)

Deliverable:
- Stable daily batch with quality report

## Phase 4: Scale-out (Week 3+)
1. Move DB to PostgreSQL
2. Introduce queue workers (DB queue backend or external broker)
3. Split scheduler, scraper workers, and export workers
4. Add dashboards and alerting

Deliverable:
- 100k leads/day architecture ready

## Logical implementation order in code
1. `winxtract/storage/db.py`
2. `winxtract/scrapers/base.py`, `registry.py`
3. `winxtract/core/browser_pool.py`, `rate_limit.py`, `robots.py`
4. `winxtract/core/pipeline.py`, parsers, scoring, dedupe
5. `winxtract/orchestrator/job_runner.py`
6. `winxtract/cli.py`
7. source plugins + source YAML
8. exports + monitoring + tests

## MVP done criteria
- Public-only sources configured
- Retry + timeout + per-domain delay active
- Dedupe and score stored in DB
- Export works in 3 formats
- Structured logs emitted for jobs and errors
