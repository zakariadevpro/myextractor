from winxtract.core.models import RawRecord
from winxtract.core.pipeline import Pipeline


def test_particulier_mode_drops_person_record():
    pipeline = Pipeline(
        source_params={
            "privacy_mode": "particulier_conforme",
            "privacy_drop_person_records": True,
        }
    )
    raw = RawRecord(
        source_slug="s1",
        page_url="https://example.com/profile/123?token=abc",
        payload={
            "name": "Jean Dupont",
            "city": "Paris",
            "phone": "06 12 34 56 78",
            "full_text": "Jean Dupont 06 12 34 56 78 jean.dupont@gmail.com",
            "address": "12 rue Exemple Paris",
        },
    )
    assert pipeline.process_record(raw) is None


def test_particulier_mode_redacts_sensitive_fields():
    pipeline = Pipeline(
        source_params={
            "privacy_mode": "particulier_conforme",
            "privacy_drop_person_records": True,
            "privacy_redact_contact": True,
            "privacy_redact_address": True,
            "privacy_redact_page_url": True,
            "privacy_sanitize_description": True,
        }
    )
    raw = RawRecord(
        source_slug="s1",
        page_url="https://example.com/listing/42?foo=bar",
        payload={
            "name": "SARL Dupont Services",
            "city": "Paris",
            "phone": "01 44 55 66 77",
            "website": "https://dupont.example",
            "full_text": "SARL Dupont Services contact@societe.fr 01 44 55 66 77",
            "address": "20 avenue test",
        },
    )
    lead = pipeline.process_record(raw)
    assert lead is not None
    assert lead.name == "SARL Dupont Services"
    assert lead.emails == []
    assert lead.phones == []
    assert lead.address is None
    assert lead.page_url == "https://example.com/"
    assert "[redacted-email]" in (lead.description or "")


def test_b2c_etendu_profile_keeps_person_but_redacts_contact():
    pipeline = Pipeline(
        source_params={
            "privacy_profile": "b2c_etendu",
        }
    )
    raw = RawRecord(
        source_slug="s1",
        page_url="https://example.com/profile/42?foo=bar",
        payload={
            "name": "Jean Dupont",
            "city": "Paris",
            "phone": "06 12 34 56 78",
            "full_text": "Jean Dupont 06 12 34 56 78 jean.dupont@gmail.com",
            "address": "12 rue Exemple Paris",
        },
    )
    lead = pipeline.process_record(raw)
    assert lead is not None
    assert lead.name == "Jean Dupont"
    assert lead.emails == []
    assert lead.phones == []
    assert lead.address == "12 rue Exemple Paris"
    assert lead.page_url == "https://example.com/profile/42?foo=bar"
