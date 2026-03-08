from app.services.meta_lead_ads_service import MetaLeadAdsService


def test_meta_mapper_builds_intake_payload_from_field_data():
    service = MetaLeadAdsService(access_token="")
    payload = service.build_intake_payload(
        leadgen_id="123456",
        field_data_rows=[
            {"name": "full_name", "values": ["Jean Dupont"]},
            {"name": "email", "values": ["jean.dupont@example.com"]},
            {"name": "phone_number", "values": ["+33611223344"]},
            {"name": "city", "values": ["Paris"]},
            {"name": "consent_text_version", "values": ["v1.3"]},
            {"name": "privacy_policy_version", "values": ["pp-2026-01"]},
            {"name": "double_opt_in", "values": ["true"]},
        ],
        created_time="2026-03-01T10:30:00+0000",
        campaign_name="meta_campaign_test",
        source_channel="facebook",
    )

    assert payload.full_name == "Jean Dupont"
    assert payload.email == "jean.dupont@example.com"
    assert payload.consent_source == "meta_lead_ads"
    assert payload.consent_proof_ref == "meta:123456"
    assert payload.double_opt_in is True
    assert payload.source_campaign == "meta_campaign_test"
