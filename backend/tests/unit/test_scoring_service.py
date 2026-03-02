"""Unit tests for the scoring service."""

from unittest.mock import MagicMock

from app.services.scoring_service import ScoringService


def _make_lead(**kwargs):
    """Create a mock lead for testing."""
    lead = MagicMock()
    lead.emails = kwargs.get("emails", [])
    lead.phones = kwargs.get("phones", [])
    lead.website = kwargs.get("website", None)
    lead.address = kwargs.get("address", None)
    lead.postal_code = kwargs.get("postal_code", None)
    lead.city = kwargs.get("city", None)
    lead.siren = kwargs.get("siren", None)
    lead.naf_code = kwargs.get("naf_code", None)
    lead.sector = kwargs.get("sector", None)
    lead.source = kwargs.get("source", None)
    lead.is_duplicate = kwargs.get("is_duplicate", False)
    return lead


def _make_email(valid=True):
    e = MagicMock()
    e.is_valid = valid
    return e


def _make_phone(phone_type="landline"):
    p = MagicMock()
    p.phone_type = phone_type
    p.is_valid = True
    return p


class TestScoringService:
    def setup_method(self):
        self.service = ScoringService(db=MagicMock())

    def test_empty_lead_scores_zero(self):
        lead = _make_lead()
        assert self.service.calculate_score(lead) == 0

    def test_valid_email_increases_score(self):
        base = _make_lead(source="whiteextractor")
        lead = _make_lead(emails=[_make_email(valid=True)], source="whiteextractor")
        assert self.service.calculate_score(lead) > self.service.calculate_score(base)

    def test_phone_increases_score(self):
        base = _make_lead(source="whiteextractor")
        lead = _make_lead(phones=[_make_phone("mobile")], source="whiteextractor")
        assert self.service.calculate_score(lead) > self.service.calculate_score(base)

    def test_phone_type_impacts_score(self):
        mobile = _make_lead(phones=[_make_phone("mobile")], source="whiteextractor")
        landline = _make_lead(phones=[_make_phone("landline")], source="whiteextractor")
        assert self.service.calculate_score(mobile) >= self.service.calculate_score(landline)

    def test_website_increases_score(self):
        base = _make_lead(source="whiteextractor")
        lead = _make_lead(website="https://example.com", source="whiteextractor")
        assert self.service.calculate_score(lead) > self.service.calculate_score(base)

    def test_complete_address_increases_score(self):
        base = _make_lead(source="whiteextractor")
        lead = _make_lead(
            address="1 rue Test",
            postal_code="75001",
            city="Paris",
            source="whiteextractor",
        )
        assert self.service.calculate_score(lead) > self.service.calculate_score(base)

    def test_siren_increases_score(self):
        base = _make_lead(source="whiteextractor")
        lead = _make_lead(siren="123456789", source="whiteextractor")
        assert self.service.calculate_score(lead) > self.service.calculate_score(base)

    def test_premium_sector_increases_score(self):
        base = _make_lead(source="whiteextractor")
        lead = _make_lead(sector="immobilier", source="whiteextractor")
        assert self.service.calculate_score(lead) > self.service.calculate_score(base)

    def test_whiteextractor_source_bonus(self):
        white = _make_lead(source="whiteextractor")
        generic = _make_lead(source="unknown")
        assert self.service.calculate_score(white) > self.service.calculate_score(generic)

    def test_duplicate_penalty_reduces_score(self):
        rich = _make_lead(
            emails=[_make_email(valid=True)],
            phones=[_make_phone("mobile")],
            website="https://example.com",
            source="sirene_api",
            is_duplicate=False,
        )
        duplicate = _make_lead(
            emails=[_make_email(valid=True)],
            phones=[_make_phone("mobile")],
            website="https://example.com",
            source="sirene_api",
            is_duplicate=True,
        )
        assert self.service.calculate_score(duplicate) < self.service.calculate_score(rich)

    def test_max_score_is_100(self):
        lead = _make_lead(
            emails=[_make_email(valid=True)],
            phones=[_make_phone("landline")],
            website="https://example.com",
            address="1 rue Test",
            postal_code="75001",
            city="Paris",
            siren="123456789",
            sector="immobilier",
        )
        score = self.service.calculate_score(lead)
        assert score <= 100

    def test_full_lead_high_score(self):
        lead = _make_lead(
            emails=[_make_email(valid=True)],
            phones=[_make_phone("landline")],
            website="https://example.com",
            address="1 rue Test",
            postal_code="75001",
            city="Paris",
            siren="123456789",
            sector="immobilier",
            source="whiteextractor",
        )
        score = self.service.calculate_score(lead)
        assert score >= 80
