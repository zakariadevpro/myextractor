import pytest

from app.models.lead import Lead, LeadEmail
from app.models.organization import Organization


@pytest.mark.asyncio
async def test_api_key_scope_and_public_leads_access(client, db_session, test_org, auth_headers):
    lead = Lead(
        organization_id=test_org.id,
        company_name="ACME Test",
        source="whiteextractor",
        quality_score=87,
        city="Paris",
        lead_kind="b2b",
    )
    lead.emails = [LeadEmail(email="contact@acme.test", is_valid=True, is_primary=True)]
    db_session.add(lead)

    other_org = Organization(name="Other Org", slug="other-org-test")
    db_session.add(other_org)
    await db_session.flush()
    db_session.add(
        Lead(
            organization_id=other_org.id,
            company_name="Other Corp",
            source="whiteextractor",
            quality_score=95,
            city="Lyon",
            lead_kind="b2b",
        )
    )
    await db_session.flush()

    create = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Public Read", "scopes": ["leads:read"]},
    )
    assert create.status_code == 200
    created = create.json()
    assert created["api_key"].startswith("wk_live_")
    key_id = created["key"]["id"]

    list_response = await client.get(
        "/api/v1/public/leads",
        headers={"X-API-Key": created["api_key"]},
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["company_name"] == "ACME Test"

    export_denied = await client.get(
        "/api/v1/public/leads/export/csv",
        headers={"X-API-Key": created["api_key"]},
    )
    assert export_denied.status_code == 403
    assert "leads:export" in export_denied.json()["detail"]

    revoke = await client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=auth_headers)
    assert revoke.status_code == 200

    after_revoke = await client.get(
        "/api/v1/public/leads",
        headers={"X-API-Key": created["api_key"]},
    )
    assert after_revoke.status_code == 401


@pytest.mark.asyncio
async def test_workflow_manual_run_updates_only_matching_leads(
    client, db_session, test_org, auth_headers
):
    lead_match = Lead(
        organization_id=test_org.id,
        company_name="Lead Match",
        source="web_form",
        quality_score=20,
        city="Paris",
        lead_kind="b2b",
    )
    lead_match.emails = [LeadEmail(email="lead.match@test.local", is_valid=True, is_primary=True)]

    lead_missing_email = Lead(
        organization_id=test_org.id,
        company_name="Lead No Email",
        source="web_form",
        quality_score=20,
        city="Paris",
        lead_kind="b2b",
    )
    lead_other_city = Lead(
        organization_id=test_org.id,
        company_name="Lead Other City",
        source="web_form",
        quality_score=20,
        city="Lyon",
        lead_kind="b2b",
    )
    db_session.add_all([lead_match, lead_missing_email, lead_other_city])
    await db_session.flush()

    create = await client.post(
        "/api/v1/workflows",
        headers=auth_headers,
        json={
            "name": "Manual Workflow",
            "trigger_event": "manual",
            "conditions": {"city_contains": "par", "has_email": True},
            "actions": {"score_delta": 15, "set_source": "workflow_rule", "mark_duplicate": True},
        },
    )
    assert create.status_code == 200

    dry_run = await client.post(
        "/api/v1/workflows/run",
        headers=auth_headers,
        json={"dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_body = dry_run.json()
    assert dry_body["total_workflows"] == 1
    assert dry_body["total_matched"] == 1
    assert dry_body["total_updated"] == 0

    run = await client.post(
        "/api/v1/workflows/run",
        headers=auth_headers,
        json={"dry_run": False},
    )
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["total_workflows"] == 1
    assert run_body["total_matched"] == 1
    assert run_body["total_updated"] == 1

    await db_session.flush()
    await db_session.refresh(lead_match)
    await db_session.refresh(lead_missing_email)
    await db_session.refresh(lead_other_city)

    assert lead_match.quality_score == 35
    assert lead_match.source == "workflow_rule"
    assert lead_match.is_duplicate is True
    assert lead_missing_email.quality_score == 20
    assert lead_other_city.quality_score == 20


@pytest.mark.asyncio
async def test_scoring_profile_update_and_recompute(client, db_session, test_org, auth_headers):
    lead = Lead(
        organization_id=test_org.id,
        company_name="Score Me",
        source="unknown",
        quality_score=0,
        city="Paris",
        lead_kind="b2b",
    )
    lead.emails = [LeadEmail(email="score.me@test.local", is_valid=True, is_primary=True)]
    db_session.add(lead)
    await db_session.flush()

    current = await client.get("/api/v1/scoring/profile", headers=auth_headers)
    assert current.status_code == 200
    current_body = current.json()
    assert current_body["high_threshold"] == 80
    assert current_body["medium_threshold"] == 55

    update = await client.put(
        "/api/v1/scoring/profile",
        headers=auth_headers,
        json={
            "name": "Aggressive",
            "high_threshold": 75,
            "medium_threshold": 45,
            "weights": {
                "valid_email": 35,
                "fallback_source_bonus": 0,
                "no_contact_penalty": 20,
            },
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["name"] == "Aggressive"
    assert updated["high_threshold"] == 75
    assert updated["medium_threshold"] == 45
    assert updated["weights"]["valid_email"] == 35
    assert updated["weights"]["fallback_source_bonus"] == 0

    recompute = await client.post("/api/v1/scoring/recompute", headers=auth_headers)
    assert recompute.status_code == 200
    assert recompute.json()["scored"] == 1

    await db_session.flush()
    await db_session.refresh(lead)
    assert lead.quality_score == 35
