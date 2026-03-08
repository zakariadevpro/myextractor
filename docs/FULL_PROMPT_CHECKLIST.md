# WinXtract Full Prompt Checklist

Date: 2026-03-06

## 1) Scalabilite (1k -> 100k leads/jour)

- Queue persistante DB disponible (`WINXTRACT_TASK_BACKEND=db_queue`)
- Workers multiples supportes (`winxtract queue-worker` lance en parallel)
- Monitoring de charge via `winxtract load-test`
- Dead-letter queue active (statut terminal `dead` apres max retries)

## 2) PostgreSQL production

- Driver PostgreSQL ajoute (`psycopg[binary]`)
- Stack Docker production fournie (`docker-compose.prod.yml`)
- Services UI/worker relies a PostgreSQL

## 3) Logging & monitoring avance

- Endpoint Prometheus: `/metrics/prometheus`
- Endpoint monitoring consolide: `/api/v1/monitoring/summary`
- Prometheus/Grafana configures dans `ops/monitoring/`

## 4) UI source health

- Page UI: `/source-health`
- Auto-disable manuel depuis UI (seuil configurable)
- Endpoint API: `/api/v1/source-health`

## 5) Pack sources supplementaires

- Catalogue stable/candidate: `config/source_catalog.yaml`
- Commande listing: `winxtract source-catalog`
- Pack etendu de sources candidates (disabled par defaut):
  - `recherche_entreprises_boulangerie_lyon`
  - `recherche_entreprises_coiffure_marseille`
  - `recherche_entreprises_restaurants_lille`
  - `recherche_entreprises_garages_nice`
  - `recherche_entreprises_dentistes_toulouse`
  - `recherche_entreprises_pharmacies_nantes`
  - `overpass_osm_lyon_shops`
  - `overpass_osm_marseille_shops`

## 6) Tests de charge

- CLI: `winxtract load-test --action run-export-stable --requests-count 200 --concurrency 25`
- Mesures: status codes, latence avg/p50/p95

## 7) Conformite (durcissement export)

- Regle configurable: `WINXTRACT_EXPORT_REQUIRED_PRIVACY_MODE=particulier_conforme`
- Si active, export bloque pour sources non conformes

## 8) Demarrage automatique services

- Start/Stop scripts Windows:
  - `ops/windows/start_winxtract_services.ps1`
  - `ops/windows/stop_winxtract_services.ps1`
- Installation startup task:
  - `ops/windows/install_winxtract_startup_tasks.ps1`
