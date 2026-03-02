# Winaity Extractor - B2C Quickstart (Mode Safe)

## Ce qui est actif
- `lead_kind`: chaque lead est tagge `b2b` ou `b2c`
- Endpoint intake B2C consentie: `POST /api/v1/leads/b2c/intake`
- Garde-fou: le mode B2C doit etre actif via `B2C_MODE_ENABLED=true`
- B2B scraping reste separe (sources extraction classiques)

## Variables d'environnement
Dans `.env`:

```env
B2C_MODE_ENABLED=true
CONSENT_ENFORCEMENT_ENABLED=false
B2C_WEBHOOK_SECRET=change-me-webhook-secret
META_WEBHOOK_VERIFY_TOKEN=change-me-meta-verify-token
META_ACCESS_TOKEN=
```

`CONSENT_ENFORCEMENT_ENABLED` ne bloque pas l'intake B2C, mais reste utile pour verrouiller les exports.

## Payload attendu (B2C consentie)

```json
{
  "full_name": "Jean Dupont",
  "email": "jean.dupont@example.com",
  "phone": "+33611223344",
  "city": "Paris",
  "consent_source": "web_form",
  "consent_at": "2026-03-01T10:30:00Z",
  "consent_text_version": "v1.2",
  "consent_proof_ref": "form-20260301-0001",
  "privacy_policy_version": "pp-2026-01",
  "source_campaign": "landing_assurance_auto",
  "source_channel": "web",
  "purpose": "prospection_commerciale",
  "double_opt_in": true,
  "double_opt_in_at": "2026-03-01T10:35:00Z"
}
```

Contraintes:
- au moins `email` ou `phone`
- `consent_proof_ref` doit etre unique par organisation/source
- `consent_status` et `lawful_basis` sont fixes automatiquement a `granted` et `consent`

## Exemple PowerShell

```powershell
$token = "<ACCESS_TOKEN>"
$body = @{
  full_name = "Jean Dupont"
  email = "jean.dupont@example.com"
  phone = "+33611223344"
  city = "Paris"
  consent_source = "web_form"
  consent_at = "2026-03-01T10:30:00Z"
  consent_text_version = "v1.2"
  consent_proof_ref = "form-20260301-0001"
  privacy_policy_version = "pp-2026-01"
  source_campaign = "landing_assurance_auto"
  source_channel = "web"
  purpose = "prospection_commerciale"
  double_opt_in = $true
  double_opt_in_at = "2026-03-01T10:35:00Z"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:18000/api/v1/leads/b2c/intake" `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body $body
```

## Filtrage dans l'UI
La liste leads supporte maintenant:
- `Type = B2B`
- `Type = B2C`
- `Tous (B2B + B2C)`

## Saisie depuis l'interface
Dans `Extraction`, une carte `Intake B2C Consentie` est disponible pour inserer un contact B2C sans passer par API.

## Webhook intake B2C (partenaire/formulaires)
Endpoint:

- `POST /api/v1/webhooks/b2c/intake/{org_slug}`
- Header requis: `X-Winaity-Webhook-Secret: <B2C_WEBHOOK_SECRET>`

Le payload est le meme que `POST /api/v1/leads/b2c/intake`.

## Meta Lead Ads (safe mode)
Verification Meta:

- `GET /api/v1/webhooks/meta/lead-ads/{org_slug}?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`

Reception evenements:

- `POST /api/v1/webhooks/meta/lead-ads/{org_slug}`
- Header requis: `X-Winaity-Webhook-Secret`

Comportement:

1. Si `META_ACCESS_TOKEN` est defini, le serveur recupere les details lead via Graph API.
2. Sinon, il accepte un `lead_data` inline dans l'evenement (mode relay/server-to-server).
3. Les leads sont ingeres en `lead_kind=b2c` avec consentement `granted`.
4. Doublons de preuve (`consent_proof_ref`) sont bloques.

## Dashboard conformite
Nouveau endpoint:

- `GET /api/v1/dashboard/b2c-compliance`

Expose:

- total B2C
- consentis / refuses / revoques / inconnus
- exportables
- expirations retention < 7 jours
- taux double opt-in
- taux revocation
- repartition par source de consentement
