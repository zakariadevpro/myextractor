# Winaity Extractor - Sources B2C Safe + Modele Consentement

## Objectif
Permettre l'extraction B2C sans risque legal majeur, en n'ingestant que des contacts avec base legale explicite (opt-in, contrat, interet legitime prouve selon usage).

## Sources B2C recommandees (safe)
1. Formulaires first-party (site, landing pages, quiz, demande devis)
2. Lead Ads officielles (Meta Lead Ads, Google Lead Form, TikTok Lead Gen)
3. Plateformes partenaires avec DPA/contrat + preuve de consentement
4. Import CRM interne (contacts existants avec historique de consentement)
5. Webhooks partenaires (events explicites: `lead.created`, `consent.granted`, `consent.revoked`)

## Sources a exclure (ou mode interdit)
1. Scraping reseaux sociaux de profils prives
2. Scraping annuaires perso sans base legale claire
3. Achat de fichiers sans traçabilite du consentement
4. Enrichissement invasif sans finalite declaree

## Modele minimal de consentement (a stocker par contact)
Champs obligatoires:
- `consent_status` : `granted | denied | revoked | unknown`
- `consent_scope` : `email | phone | sms | whatsapp | all`
- `consent_source` : `web_form | meta_ads | google_ads | import | partner_api`
- `consent_at` : datetime UTC du consentement
- `consent_text_version` : version du texte legal accepte
- `consent_proof_ref` : id de preuve (event id, form submission id, ad lead id)
- `privacy_policy_version` : version de politique de confidentialite
- `lawful_basis` : `consent | contract | legitimate_interest`

Champs fortement recommandes:
- `source_campaign` : nom/id campagne
- `source_channel` : `facebook | instagram | google | tiktok | web`
- `ip_hash` : hash ip (pas IP brute)
- `user_agent_hash` : hash user-agent
- `double_opt_in` : bool
- `double_opt_in_at` : datetime UTC
- `purpose` : ex. `prospection_commerciale`
- `data_retention_until` : datetime UTC

## Regles de blocage (garde-fous)
1. `consent_status != granted` => pas d'appel sortant, pas d'email marketing
2. `double_opt_in = true` requis pour campagnes sensibles (email massif)
3. `lawful_basis = consent` obligatoire pour canaux marketing directs
4. `consent_text_version` absent => contact non activable
5. `consent_revoked` recu => blocage immediat + propagation vers dialer/campagnes

## Mapping rapide dans Winaity Extractor
- Ajouter un objet `lead_consent` lie a chaque lead/contact
- Alimenter via connecteurs:
  - `connectors/meta_lead_ads`
  - `connectors/google_lead_forms`
  - `connectors/web_forms`
  - `connectors/partner_webhooks`
- Ajouter checks backend avant:
  - export CSV
  - push vers call center
  - lancement campagne

## Contrats/API a prioriser
1. Meta Marketing API (Lead Ads webhook + pull fallback)
2. Google Ads Lead Form extensions (via integration officielle)
3. Form provider webhook (Typeform/Jotform/Gravity Forms)
4. Connecteur interne CRM import avec validation schema consent

## Plan implementation (ordre recommande)
1. Schema DB consent + migration
2. Endpoints API consent (`GET/PATCH /leads/{id}/consent`)
3. Guard backend de blocage avant export/push
4. Connecteur Web Form (le plus rapide a livrer)
5. Connecteur Meta Lead Ads
6. Journal audit: `consent.granted`, `consent.updated`, `consent.revoked`
7. Dashboard compliance: taux opt-in, taux revocation, contacts non activables

