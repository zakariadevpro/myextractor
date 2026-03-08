# Winaity Extractor - Proposition moderne (V1 evolutive)

Objectif: avancer vite sans figer trop tot les choix UI/metier.

## 1. Architecture produit recommandee
- `Core CRM`: leads, filtres, qualification, export.
- `Extraction Engine`: jobs, sources, quotas, priorites.
- `Governance`: audit, roles, securite session, billing.
- `Integrations`: webhooks, API, white-label.

## 2. Parcours utilisateurs cible
- `Admin`: pilote securite, equipe, abonnement, supervision.
- `Manager`: lance extractions, valide qualite, exporte.
- `User`: consulte leads et avancement jobs.

## 3. UX moderne proposee
- Sidebar metier stable: Dashboard, Leads, Extraction, Audit, Parametres.
- Pages orientees action: KPIs, filtres persistants, feedback temps reel.
- Controle des permissions en UI + API pour eviter les erreurs 403.
- Navigation orientee persona:
  - `user`: lecture, qualification, consultation
  - `manager`: operations extraction + controle qualite
  - `admin`: gouvernance, equipe, facturation, audit

## 4. Fiabilite et securite
- Auth robuste: rotation refresh + option cookie/CSRF.
- Audit complet des actions sensibles.
- Contraintes DB pour integrite (roles, subscriptions actives).

## 5. Evolution sans casse
- Feature flags pour activer modules par client.
- Contrats API stables (`/api/v1`) + versionnage schema.
- Backlog decisions maintenu dans `ARCHITECTURE_DECISIONS_BACKLOG.md`.
