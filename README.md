# Winaity-Extractor

Projet CRM d'extraction de leads, isole de `Win-CRM`.

## Ports (anti-conflit Win-CRM)

- Frontend: `15173` (au lieu de `5173`)
- Backend API: `18000` (au lieu de `8000`)
- PostgreSQL: `55432` (au lieu de `5432`)
- Redis: `16379` (au lieu de `6379`)

## Demarrage Docker

1. Copier l'environnement:

```bash
cp .env.example .env
```

2. Mode stable (recommande, sans coupure de chunks):

```bash
docker-compose up -d --build
```

3. Mode dev frontend (hot reload):

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build frontend
```

4. Verifier:

- Frontend: `http://localhost:15173`
- API: `http://localhost:18000/api/v1`

## Raccourcis PowerShell (Windows)

```powershell
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$proj = "C:\xampp\mysql\data\Winaity Extractor"

# Mode stable
& $docker compose -f "$proj\docker-compose.yml" up -d --build

# Mode dev frontend (hot reload)
& $docker compose -f "$proj\docker-compose.yml" -f "$proj\docker-compose.dev.yml" up -d --build frontend
```

## Docs

- Mode extraction recommande (type WhiteExtractor): source `whiteextractor` (fusion Sirene + Pages Jaunes + Google Maps)
- API publique securisee (API keys), workflows auto, scoring IA v2: `docs/API_AUTOMATION_SCORING_V2.md`
- Baseline production SaaS: `docs/PROD_SAAS_BASELINE.md`
- Backlog decisions architecture/produit: `docs/ARCHITECTURE_DECISIONS_BACKLOG.md`
- Proposition produit moderne V1: `docs/PRODUCT_STRATEGY_V1.md`
- Sources B2C safe + modele consentement: `docs/B2C_SAFE_SOURCES_AND_CONSENT.md`
- Mise en route B2C (API intake consentie): `docs/B2C_SYSTEM_QUICKSTART.md`
