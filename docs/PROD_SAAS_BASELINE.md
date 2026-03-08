# Winaity Extractor - Baseline Production (SaaS)

Cette checklist est la base minimale avant mise en production.

## 1. Verrouiller les secrets
- Régénérer `JWT_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, mots de passe DB/Redis.
- Interdire les secrets par défaut dans `.env`.
- Préparer rotation JWT:
  - `JWT_ACTIVE_KID` courant
  - `JWT_PREVIOUS_SECRET_KEY` pendant la fenêtre de transition

## 2. Migrations obligatoires
- Exécuter:
  - `alembic upgrade head`
- Vérifier la présence de:
  - `audit_logs`
  - contrainte `ck_users_role_valid`
  - index `uq_subscriptions_active_org`

## 3. TLS et domaines
- Forcer HTTPS (Nginx ou reverse proxy).
- Certificat valide (Let's Encrypt ou PKI interne).
- `CORS_ORIGINS` limité aux domaines front autorisés.
- Si app web: activer `AUTH_COOKIE_MODE=true` + CSRF header/cookie.

## 4. RBAC et comptes
- Rôles autorisés: `admin`, `manager`, `user` uniquement.
- Supprimer/désactiver les comptes inactifs.
- Activer rotation des mots de passe administrateurs.

## 5. Observabilité et audit
- Conserver les logs API et `audit_logs` minimum 90 jours.
- Superviser:
  - taux d'erreurs 5xx
  - tentatives de login
  - exports CSV et opérations destructives

## 6. Backups et restauration
- Backup quotidien PostgreSQL + test de restauration hebdomadaire.
- Backup de configuration applicative (`.env`, compose, reverse proxy).

## 7. Validation de release
- Vérifier:
  - `pytest backend/tests/unit -q`
  - `npx tsc --noEmit` (frontend)
  - healthchecks API/front
- Tester un flux métier complet:
  - login
  - extraction
  - export
  - droits manager/user
