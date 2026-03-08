# WinXtract

Moteur de scraping multi-sources independant pour collecter des fiches B2C
publiques accessibles sans authentification.

## Perimetre

- Donnees publiques uniquement
- Aucun contournement d'acces prive
- Respect configurable de `robots.txt`

## Stack MVP

- Python 3.11+
- Playwright (navigation et rendu JS)
- SQLAlchemy + SQLite (MVP) ou PostgreSQL (scale)
- CLI Typer

## Pipeline

`scrape -> parse -> clean -> normalize -> score -> store -> export`

## Scraper generique

- Selecteurs supportes: `css:` et `xpath:` (ou XPath brut `//...`)
- Pagination configurable:
  - `pagination_mode: click`
  - `pagination_mode: rel_next`
- Limite de pagination: `params.max_pages`

## Open Data

- Plugin dedie `open_data_json` pour endpoints JSON publics
- Extraction configurable via `selectors` (paths JSON)
- Support `params.items_path` pour cibler la liste d'enregistrements
- Pagination `offset` supportee via:
  - `params.pagination_mode: offset`
  - `params.page_size`
  - `params.max_pages`
  - `params.limit_param` / `params.offset_param`
- Plugin `data_gouv_dataset` pour ingerer un dataset `data.gouv.fr` (metadata -> resource CSV/JSON)
- Pack ARCEP initial: `data_gouv_arcep_points_mutualisation.yaml`
- Plugin `recherche_entreprises_api` pour l'API publique `recherche-entreprises.api.gouv.fr`
- Expansion geographique via fichiers de villes (`params.cities_file`), ex: `config/geo/france_prefectures.txt`
- Seed nationaux particuliers possibles via `params.seed_names_file` + `params.cities_file` (ex: Pages Blanches)

## Particulier conforme

Pipeline conforme activable globalement ou par source:

- Variable globale: `WINXTRACT_PRIVACY_MODE=particulier_conforme`
- Param source: `params.privacy_mode: particulier_conforme`
- Profil source: `params.privacy_profile: b2c_conforme|b2c_etendu`
- Proxy optionnel (si blocage IP): `WINXTRACT_PROXY_URL=http://user:pass@host:port`

Actions automatiques en mode conforme:

- Filtrage des fiches probables de particuliers (nom de personne)
- Filtrage des fiches avec email perso (gmail/outlook/... configurable)
- Redaction contacts (`emails`, `phones`)
- Redaction `address`
- Redaction `page_url` vers domaine seul
- Nettoyage de `description` (email/telephone masques)

Profils predefinis:

- `b2c_conforme` (recommande): filtrage fort + redaction maximale
- `b2c_etendu`: filtrage plus permissif, tout en masquant les contacts

## Blocages anti-bot / robots

- WinXtract detecte maintenant explicitement les pages challenge (`403`, `captcha`, `just a moment`, `noindex,nofollow`) et remonte une erreur claire.
- Si une source est bloquee depuis ton IP, privilegier les APIs/open-data officielles ou utiliser un proxy autorise via `WINXTRACT_PROXY_URL`.

## Installation rapide

```bash
cd WinXtract
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
python -m playwright install chromium
```

## Commandes

```bash
winxtract init-db
winxtract run --sources-dir config/sources
winxtract run --sources-dir config/sources --source annuaire_118000_paris_martin
winxtract run --sources-dir config/sources --source opendata_paris_commerces_semaest
winxtract run --sources-dir config/sources --source arcep_points_mutualisation
winxtract run --sources-dir config/sources --source recherche_entreprises_fr_b2c
winxtract run --sources-dir config/sources --source opendata_bordeaux_etablissements
winxtract run --sources-dir config/sources --source overpass_osm_paris_shops
winxtract privacy-profile --profile b2c_conforme
winxtract privacy-profile --profile b2c_etendu --source pages_blanches_seed
winxtract export --format csv --output exports/leads.csv --min-score 40
winxtract quality-report --source opendata_paris_commerces_semaest --output reports/quality.json
winxtract source-health --window-jobs 10 --auto-disable-failures 3 --apply-changes
winxtract source-catalog --status stable
winxtract queue-list --limit 20
winxtract queue-worker --sources-dir config/sources
winxtract load-test --action run-export-all --requests-count 200 --concurrency 25
winxtract ui --host 127.0.0.1 --port 8787
```

## Queue persistante (optionnelle)

Par defaut, la UI execute les taches en queue locale (`thread`).
Pour une queue persistante en base (services separes), activer:

```bash
set WINXTRACT_TASK_BACKEND=db_queue
```

Puis lancer dans 2 terminaux:

```bash
winxtract ui --host 127.0.0.1 --port 8787
winxtract queue-worker --sources-dir config/sources
```

Notes:

- Les actions UI/API (`run`, `export`, `run+export`) sont mises en `queue_tasks`.
- Le worker consomme la queue avec retry + backoff exponentiel.
- Les echecs terminaux passent en statut `dead` (dead-letter) apres max retries.
- Inspection: `winxtract queue-list` et `GET /api/v1/tasks`.
- Le mode `thread` reste disponible pour usage local simple.
- Commande catalogue: `winxtract source-catalog --status candidate`

Conformite export (durcissement optionnel):

- `WINXTRACT_EXPORT_REQUIRED_PRIVACY_MODE=particulier_conforme`
- Quand active, les exports sont bloques si une source cible n'a pas ce `privacy_mode`.

## Interface graphique

Installer les dependances UI/API:

```bash
python -m pip install -e .[api]
```

Lancer l'interface:

```bash
winxtract ui --host 127.0.0.1 --port 8787
```

Puis ouvrir `http://127.0.0.1:8787`.

Fonctions UI:

- Dashboard KPI (leads, jobs, erreurs)
- Lancement de scrape depuis le navigateur
- Export CSV / JSON / XLSX
- Activation / desactivation des sources
- Page des logs d'erreurs: `/errors`
- Page de consultation leads: `/leads`
- Page de suivi des taches UI: `/tasks`
- Page dead-letter queue: `/dead-letters` (requeue manuel)
- Page scheduler: `/scheduler`
- Page qualite data: `/quality`
- Page source health: `/source-health`
- Liens de telechargement des exports depuis le dashboard
- Action combinee: `Run + Export auto` en un clic
- Action combinee: `Run France entiere + Export auto` en un clic
- Action UI: `Profil B2C` pour appliquer `b2c_conforme` ou `b2c_etendu` (une source ou toutes)
- Actions lancees en mode asynchrone (queue UI non bloquante)
- Schedules stockes dans `config/schedules.yaml`
- Endpoint metrics JSON: `/metrics/json`
- Endpoint metrics Prometheus: `/metrics/prometheus`
- Endpoint monitoring consolide: `/api/v1/monitoring/summary`
- Backend de taches configurable: `thread` (local) ou `db_queue` (persistant)

## API externe (`/api/v1`)

Endpoints principaux:

- `GET /api/v1/health`
- `GET /api/v1/sources`
- `GET /api/v1/jobs`
- `GET /api/v1/leads`
- `GET /api/v1/errors`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/dead-letters`
- `POST /api/v1/tasks/{task_id}/requeue`
- `POST /api/v1/tasks/requeue-batch`
- `GET /api/v1/exports`
- `GET /api/v1/quality`
- `GET /api/v1/source-health`
- `GET /api/v1/monitoring/summary`
- `POST /api/v1/actions/run`
- `POST /api/v1/actions/export`
- `POST /api/v1/actions/run-export`
- `POST /api/v1/actions/run-export-all`
- `POST /api/v1/actions/run-export-stable`

Securite API:

- Token optionnel via `WINXTRACT_API_TOKEN`
- Header supporte:
  - `X-API-Key: <token>`
  - `Authorization: Bearer <token>`
- Rate limit par minute via `WINXTRACT_API_RATE_LIMIT_PER_MINUTE`

Exemples rapides:

```bash
curl http://127.0.0.1:8787/api/v1/leads?source_slug=annuaire_118000_paris_martin&limit=20
curl -X POST http://127.0.0.1:8787/api/v1/actions/run-export -H "Content-Type: application/json" -d "{\"source_slug\":\"annuaire_118000_paris_martin\",\"export_format\":\"csv\",\"min_score\":0}"
curl -X POST http://127.0.0.1:8787/api/v1/actions/run-export-all -H "Content-Type: application/json" -d "{\"export_format\":\"csv\",\"min_score\":0}"
curl -X POST http://127.0.0.1:8787/api/v1/actions/run-export-stable -H "Content-Type: application/json" -d "{\"export_format\":\"csv\",\"min_score\":0}"
curl http://127.0.0.1:8787/api/v1/tasks
curl "http://127.0.0.1:8787/api/v1/source-health?window_jobs=10&auto_disable_failures=3"
curl "http://127.0.0.1:8787/api/v1/monitoring/summary"
curl http://127.0.0.1:8787/api/v1/jobs -H "X-API-Key: YOUR_TOKEN"
curl "http://127.0.0.1:8787/api/v1/leads?source_slug=opendata_paris_commerces_semaest&has_phone=false&city=Paris&limit=20"
```

Filtres export supportes (CLI/API/UI):

- `source_slug`
- `min_score`
- `city`
- `has_email`
- `has_phone`
- `date_from` (ISO)
- `date_to` (ISO)
- `name_contains`

## Dossiers

- `winxtract/scrapers`: scrapers plugins
- `winxtract/core`: infra navigateur, retry, rate-limit, pipeline
- `winxtract/storage`: DB et export
- `config/sources`: definitions YAML de sources
- `config/source_catalog.yaml`: catalogue stable/candidate
- `ops`: scripts deploiement + monitoring
- `docs`: architecture et plan d'implementation

## Sources de depart

- `annuaire_118000_public.yaml`: active par defaut (starter)
- `pages_blanches_public.yaml`: source particuliers France seed (desactivee par defaut, anti-bot possible, profil `b2c_etendu`)
- `opendata_public_example.yaml`: exemple pour source open-data JSON
- `opendata_paris_commerces_semaest.yaml`: source open-data FR reelle (active)
- `data_gouv_arcep_points_mutualisation.yaml`: pack ARCEP via data.gouv.fr (active)
- `recherche_entreprises_public.yaml`: API entreprise.gouv (active, mode France entiere via `cities_file`)
- `recherche_entreprises_boulangerie_lyon.yaml`: candidat API publique (desactive)
- `recherche_entreprises_coiffure_marseille.yaml`: candidat API publique (desactive)
- `recherche_entreprises_restaurants_lille.yaml`: candidat API publique (desactive)
- `recherche_entreprises_garages_nice.yaml`: candidat API publique (desactive)
- `recherche_entreprises_dentistes_toulouse.yaml`: candidat API publique (desactive)
- `recherche_entreprises_pharmacies_nantes.yaml`: candidat API publique (desactive)
- `opendata_bordeaux_etablissements.yaml`: open data Bordeaux Metropole (active)
- `opendata_rennes_commerces.yaml`: open data Rennes Metropole (active)
- `overpass_osm_paris_shops.yaml`: OpenStreetMap via Overpass (active, multi-metropoles FR)
- `overpass_osm_lyon_shops.yaml`: OpenStreetMap via Overpass (candidat desactive)
- `overpass_osm_marseille_shops.yaml`: OpenStreetMap via Overpass (candidat desactive)
- `opendata_idf_professionnels_sante.yaml`: open data Ile-de-France (active)
- `opendata_strasbourg_commerces.yaml`: open data Strasbourg (active)
- `opendata_angers_associations.yaml`: open data Angers (active)
- `data_gouv_annuaire_commercants_sucy.yaml`: data.gouv annuaire commercants (active)
- `data_gouv_ameli_centres_sante.yaml`: data.gouv annuaire sante Ameli CDS (active)

Chaque source YAML peut inclure un champ `name` (nom lisible dans l'UI/API), en plus du `slug` technique.
Pour marquer une source comme recommandee, ajouter `params.stable_pack: true`.

## Deploiement production (PostgreSQL + monitoring)

Stack fournie:

- `docker-compose.prod.yml`
- `Dockerfile`
- Prometheus: `ops/monitoring/prometheus.yml`
- Grafana provisioning + dashboard: `ops/monitoring/grafana/...`

Lancement:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Acces:

- UI/API: `http://127.0.0.1:8787`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000` (`admin/admin`)

## Services Windows (UI + worker separes)

Scripts:

- Start: `ops/windows/start_winxtract_services.ps1`
- Stop: `ops/windows/stop_winxtract_services.ps1`
- Auto-start au reboot: `ops/windows/install_winxtract_startup_tasks.ps1`
