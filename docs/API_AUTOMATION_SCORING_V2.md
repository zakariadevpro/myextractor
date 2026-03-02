# API Publique + Workflows + Scoring IA v2

Ce module ajoute 3 briques cle pour Winaity Extractor:

1. API publique securisee par API keys.
2. Workflows automatiques/manuels pour transformation des leads.
3. Scoring IA v2 configurable par organisation.

## 1) API keys (admin+)

Endpoints:

- `GET /api/v1/api-keys`
- `POST /api/v1/api-keys`
- `POST /api/v1/api-keys/{key_id}/revoke`

Scopes disponibles:

- `leads:read`
- `leads:export`
- `extractions:run`
- `workflows:run`
- `scoring:read`

Utilisation API publique:

- Header requis: `X-API-Key: <cle>`
- `GET /api/v1/public/leads`
- `GET /api/v1/public/leads/export/csv`

## 2) Workflows automatiques

Endpoints:

- `GET /api/v1/workflows`
- `POST /api/v1/workflows`
- `PATCH /api/v1/workflows/{workflow_id}`
- `POST /api/v1/workflows/run` (execution manuelle)

Triggers:

- `manual`
- `post_extraction` (execute automatiquement a la fin d'un job)

Conditions supportees:

- `min_score`, `max_score`
- `lead_kind`
- `source_in` (liste)
- `city_contains`
- `has_email`, `has_phone`
- `is_duplicate`

Actions supportees:

- `score_delta`
- `set_lead_kind`
- `mark_duplicate`
- `set_source`

## 3) Scoring IA v2 configurable

Endpoints:

- `GET /api/v1/scoring/profile`
- `PUT /api/v1/scoring/profile`
- `POST /api/v1/scoring/recompute`

Parametres:

- `high_threshold`
- `medium_threshold`
- `weights` (JSON)

Le worker applique le profil de scoring en insertion, puis les workflows
`post_extraction` si actifs.

## UI

Dans le CRM:

- `Parametres > API Keys`
- `Parametres > Workflows`
- `Parametres > Scoring IA`
