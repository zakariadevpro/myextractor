import pytest

from app.config import settings


def _b2c_payload(
    *,
    full_name: str,
    email: str,
    phone: str,
    source: str,
    proof: str,
) -> dict:
    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "city": "Paris",
        "consent_source": source,
        "consent_at": "2026-03-01T10:00:00Z",
        "consent_text_version": "v1",
        "consent_proof_ref": proof,
        "privacy_policy_version": "v1",
        "source_campaign": "Campagne Test",
        "source_channel": "web",
        "purpose": "prospection_commerciale",
        "double_opt_in": False,
    }


@pytest.mark.asyncio
async def test_b2c_webhook_secret_and_duplicate_proof(client, test_org, monkeypatch):
    monkeypatch.setattr(settings, "b2c_mode_enabled", True)
    monkeypatch.setattr(settings, "b2c_webhook_secret", "test-secret")

    payload = _b2c_payload(
        full_name="Lead Webhook",
        email="lead.webhook@example.com",
        phone="+33601010101",
        source="web_form",
        proof="proof-webhook-001",
    )

    no_secret = await client.post(
        f"/api/v1/webhooks/b2c/intake/{test_org.slug}",
        json=payload,
    )
    assert no_secret.status_code == 403

    ok = await client.post(
        f"/api/v1/webhooks/b2c/intake/{test_org.slug}",
        headers={"X-Winaity-Webhook-Secret": "test-secret"},
        json=payload,
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["lead_kind"] == "b2c"
    assert body["source"] == "web_form"
    assert body["consent_status"] == "granted"

    duplicate = await client.post(
        f"/api/v1/webhooks/b2c/intake/{test_org.slug}",
        headers={"X-Winaity-Webhook-Secret": "test-secret"},
        json=payload,
    )
    assert duplicate.status_code == 400
    assert "already been ingested" in duplicate.json()["detail"]


@pytest.mark.asyncio
async def test_meta_verify_webhook_challenge_and_invalid_token(client, test_org, monkeypatch):
    monkeypatch.setattr(settings, "b2c_mode_enabled", True)
    monkeypatch.setattr(settings, "meta_webhook_verify_token", "verify-token")

    ok = await client.get(
        f"/api/v1/webhooks/meta/lead-ads/{test_org.slug}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-token",
            "hub.challenge": "abc123",
        },
    )
    assert ok.status_code == 200
    assert ok.text == "abc123"

    invalid = await client.get(
        f"/api/v1/webhooks/meta/lead-ads/{test_org.slug}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "abc123",
        },
    )
    assert invalid.status_code == 403


@pytest.mark.asyncio
async def test_meta_inline_event_ingests_b2c_lead(client, test_org, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "b2c_mode_enabled", True)
    monkeypatch.setattr(settings, "b2c_webhook_secret", "test-secret")
    monkeypatch.setattr(settings, "meta_access_token", "")

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "leadgen_id": "L-1001",
                            "lead_data": {
                                "field_data": [
                                    {"name": "full_name", "values": ["Meta Prospect"]},
                                    {
                                        "name": "email",
                                        "values": ["meta.prospect@example.com"],
                                    },
                                    {
                                        "name": "phone_number",
                                        "values": ["+33602020202"],
                                    },
                                ],
                                "created_time": "2026-03-01T11:00:00+0000",
                                "campaign_name": "Meta Camp",
                            },
                        },
                    }
                ]
            }
        ]
    }

    response = await client.post(
        f"/api/v1/webhooks/meta/lead-ads/{test_org.slug}",
        headers={"X-Winaity-Webhook-Secret": "test-secret"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processed_events"] == 1
    assert body["ingested"] == 1
    assert body["skipped"] == 0

    leads = await client.get(
        "/api/v1/leads",
        params={"lead_kind": "b2c"},
        headers=auth_headers,
    )
    assert leads.status_code == 200
    leads_body = leads.json()
    assert leads_body["total"] == 1
    assert leads_body["items"][0]["source"] == "meta_lead_ads"


@pytest.mark.asyncio
async def test_dashboard_b2c_compliance_returns_metrics(
    client,
    test_org,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "b2c_mode_enabled", True)
    monkeypatch.setattr(settings, "b2c_webhook_secret", "test-secret")

    web_payload = _b2c_payload(
        full_name="Lead Web",
        email="lead.web@example.com",
        phone="+33603030303",
        source="web_form",
        proof="proof-web-001",
    )
    meta_payload = _b2c_payload(
        full_name="Lead Meta",
        email="lead.meta@example.com",
        phone="+33604040404",
        source="meta_lead_ads",
        proof="proof-meta-001",
    )

    web_ingest = await client.post(
        f"/api/v1/webhooks/b2c/intake/{test_org.slug}",
        headers={"X-Winaity-Webhook-Secret": "test-secret"},
        json=web_payload,
    )
    assert web_ingest.status_code == 200

    meta_ingest = await client.post(
        f"/api/v1/webhooks/b2c/intake/{test_org.slug}",
        headers={"X-Winaity-Webhook-Secret": "test-secret"},
        json=meta_payload,
    )
    assert meta_ingest.status_code == 200

    compliance = await client.get(
        "/api/v1/dashboard/b2c-compliance",
        headers=auth_headers,
    )
    assert compliance.status_code == 200
    data = compliance.json()

    assert data["total_b2c"] == 2
    assert data["consent_granted"] == 2
    assert data["consent_denied"] == 0
    assert data["consent_revoked"] == 0
    assert data["consent_unknown"] == 0
    assert data["exportable_contacts"] == 2

    by_source = {row["source"]: row["count"] for row in data["by_source"]}
    assert by_source["web_form"] == 1
    assert by_source["meta_lead_ads"] == 1
