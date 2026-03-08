from winxtract.core.models import LeadData
from winxtract.core.scoring import score_lead


def test_score_increases_with_contact_fields():
    base = LeadData(source_slug="x", fingerprint="1")
    rich = LeadData(
        source_slug="x",
        fingerprint="2",
        name="Test",
        city="Paris",
        website="https://example.com",
        emails=["a@example.com"],
        phones=["+33123456789"],
        description="x" * 100,
    )
    assert score_lead(rich) > score_lead(base)
    assert score_lead(rich) <= 100
