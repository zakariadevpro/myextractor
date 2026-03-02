"""Unit tests for email validation utilities."""

from app.utils.email_validator import extract_emails_from_text, is_valid_email


class TestEmailValidation:
    def test_valid_email(self):
        assert is_valid_email("contact@example.com") is True

    def test_valid_email_subdomain(self):
        assert is_valid_email("user@mail.example.co.uk") is True

    def test_invalid_no_at(self):
        assert is_valid_email("notanemail") is False

    def test_invalid_no_domain(self):
        assert is_valid_email("user@") is False

    def test_invalid_empty(self):
        assert is_valid_email("") is False

    def test_invalid_disposable(self):
        assert is_valid_email("test@yopmail.com") is False

    def test_too_long(self):
        assert is_valid_email("a" * 300 + "@test.com") is False


class TestEmailExtraction:
    def test_extract_from_text(self):
        text = "Contactez-nous à info@example.com ou support@example.com"
        emails = extract_emails_from_text(text)
        assert "info@example.com" in emails
        assert "support@example.com" in emails

    def test_deduplicate(self):
        text = "Email: test@test.com et TEST@TEST.COM"
        emails = extract_emails_from_text(text)
        assert len(emails) == 1

    def test_no_emails(self):
        emails = extract_emails_from_text("No emails here")
        assert len(emails) == 0
