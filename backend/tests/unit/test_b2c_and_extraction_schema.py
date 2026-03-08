import pytest
from pydantic import ValidationError

from app.schemas.b2c import B2CLeadIntakeCreate
from app.schemas.extraction import ExtractionCreate


def test_b2c_intake_requires_email_or_phone():
    with pytest.raises(ValidationError):
        B2CLeadIntakeCreate(
            full_name="Jean Dupont",
            consent_source="web_form",
            consent_at="2026-03-01T10:30:00Z",
            consent_text_version="v1.2",
            consent_proof_ref="proof-001",
            privacy_policy_version="pp-2026-01",
        )


def test_b2c_intake_sets_double_opt_in_at_from_consent_at():
    payload = B2CLeadIntakeCreate(
        full_name="Jean Dupont",
        email="jean@example.com",
        consent_source="web_form",
        consent_at="2026-03-01T10:30:00Z",
        consent_text_version="v1.2",
        consent_proof_ref="proof-002",
        privacy_policy_version="pp-2026-01",
        double_opt_in=True,
    )
    assert payload.double_opt_in is True
    assert payload.double_opt_in_at == payload.consent_at


def test_extraction_source_validation_rejects_b2c_source():
    with pytest.raises(ValidationError):
        ExtractionCreate(
            source="web_form",
            keywords=["assurance"],
            city="Paris",
            radius_km=10,
            max_leads=50,
        )
