import httpx
import pytest

from app.scrapers.base import ScrapedLead
from app.scrapers.website_contact import (
    enrich_b2b_leads_with_website_emails,
    extract_emails_from_html,
    extract_emails_from_website,
    normalize_website_url,
)


def test_normalize_website_url_adds_scheme_and_rejects_non_web_links():
    assert normalize_website_url("acme.fr") == "https://acme.fr/"
    assert normalize_website_url("https://acme.fr/contact/") == "https://acme.fr/contact"
    assert normalize_website_url("mailto:contact@acme.fr") is None


def test_extract_emails_from_html_reads_mailto_and_obfuscated_text():
    html = """
    <html>
      <body>
        <a href="mailto:Contact@Acme.fr?subject=Bonjour">Email</a>
        <p>Support : support [at] acme [dot] fr</p>
        <script>var fake = "dev@example.com"</script>
      </body>
    </html>
    """

    emails = extract_emails_from_html(html)

    assert "contact@acme.fr" in emails
    assert "support@acme.fr" in emails
    assert "dev@example.com" not in emails


@pytest.mark.asyncio
async def test_extract_emails_from_website_follows_contact_link():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://acme.fr/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<a href="/contactez-nous">Contact</a>',
            )
        if str(request.url) == "https://acme.fr/contactez-nous":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<a href="mailto:hello@acme.fr">Nous ecrire</a>',
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        emails = await extract_emails_from_website("https://acme.fr", client=client)

    assert emails == ["hello@acme.fr"]


@pytest.mark.asyncio
async def test_enrich_b2b_leads_with_website_emails_skips_existing_email(monkeypatch):
    lead_with_email = ScrapedLead(
        company_name="ACME",
        website="https://acme.fr",
        emails=["existing@acme.fr"],
    )
    lead_without_email = ScrapedLead(company_name="Beta", website="https://beta.fr")

    async def fake_extract(*args, **kwargs):
        return ["contact@beta.fr"]

    monkeypatch.setattr(
        "app.scrapers.website_contact.extract_emails_from_website",
        fake_extract,
    )

    summary = await enrich_b2b_leads_with_website_emails(
        [lead_with_email, lead_without_email],
    )

    assert summary == {"checked": 1, "enriched": 1, "emails_found": 1}
    assert lead_with_email.emails == ["existing@acme.fr"]
    assert lead_without_email.emails == ["contact@beta.fr"]
