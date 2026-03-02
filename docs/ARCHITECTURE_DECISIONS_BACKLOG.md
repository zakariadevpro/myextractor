# Winaity Extractor - Backlog de decisions architecture/produit

Ce document te permet d'avancer sans bloquer le dev, meme si les choix UX/metier ne sont pas encore figes.

## 1) Modele de roles (v1 recommande)
- `admin`: configuration, billing, utilisateurs, exports.
- `manager`: operations extraction, qualite data, export CSV.
- `user`: consultation, filtres, suivi jobs.

## 2) Navigation CRM moderne (v1 recommande)
- Dashboard (KPIs + alertes qualite)
- Extractions (nouvelle extraction, historique, statuts)
- Leads (liste, filtres, enrichissement, export)
- Equipe (users + roles)
- Audit (logs securite/operations)
- Facturation (plans/usage)

## 3) Liens logiques metier
- ExtractionJob -> Leads (source de creation)
- Lead -> contacts (emails/phones) + score
- User -> AuditLog (actor)
- Organization -> toutes les ressources (isolation multi-tenant)

## 4) UX securite recommande
- Mode cookie + CSRF en production web
- Session expiration visible (toast + relogin propre)
- Confirmation obligatoire avant actions destructives
- Journal d'audit visible pour admin/manager

## 5) Roadmap fiabilite
- v1: hardening auth/rbac/audit + backup + healthchecks
- v1.1: tests integration API (auth, roles, extraction workflow)
- v1.2: observabilite (metrics + alertes erreurs + latence)
- v2: mode white-label (branding, domaine, limites par tenant)
