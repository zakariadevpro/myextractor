import logging
import re
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from app.browser.anti_detect import apply_stealth
from app.config import settings
from app.parsers.contact_parser import extract_emails, extract_phones
from app.scrapers.base import BaseScraper, ScrapedLead
from app.scrapers.proxy_pool import proxy_pool
from app.scrapers.resilience import jitter_sleep, pick_user_agent, run_with_retries

logger = logging.getLogger(__name__)

# Mapping département → région
DEPT_TO_REGION = {
    "01": "Auvergne-Rhône-Alpes",
    "03": "Auvergne-Rhône-Alpes",
    "07": "Auvergne-Rhône-Alpes",
    "15": "Auvergne-Rhône-Alpes",
    "26": "Auvergne-Rhône-Alpes",
    "38": "Auvergne-Rhône-Alpes",
    "42": "Auvergne-Rhône-Alpes",
    "43": "Auvergne-Rhône-Alpes",
    "63": "Auvergne-Rhône-Alpes",
    "69": "Auvergne-Rhône-Alpes",
    "73": "Auvergne-Rhône-Alpes",
    "74": "Auvergne-Rhône-Alpes",
    "21": "Bourgogne-Franche-Comté",
    "25": "Bourgogne-Franche-Comté",
    "39": "Bourgogne-Franche-Comté",
    "58": "Bourgogne-Franche-Comté",
    "70": "Bourgogne-Franche-Comté",
    "71": "Bourgogne-Franche-Comté",
    "89": "Bourgogne-Franche-Comté",
    "90": "Bourgogne-Franche-Comté",
    "22": "Bretagne",
    "29": "Bretagne",
    "35": "Bretagne",
    "56": "Bretagne",
    "18": "Centre-Val de Loire",
    "28": "Centre-Val de Loire",
    "36": "Centre-Val de Loire",
    "37": "Centre-Val de Loire",
    "41": "Centre-Val de Loire",
    "45": "Centre-Val de Loire",
    "08": "Grand Est",
    "10": "Grand Est",
    "51": "Grand Est",
    "52": "Grand Est",
    "54": "Grand Est",
    "55": "Grand Est",
    "57": "Grand Est",
    "67": "Grand Est",
    "68": "Grand Est",
    "88": "Grand Est",
    "02": "Hauts-de-France",
    "59": "Hauts-de-France",
    "60": "Hauts-de-France",
    "62": "Hauts-de-France",
    "80": "Hauts-de-France",
    "75": "Île-de-France",
    "77": "Île-de-France",
    "78": "Île-de-France",
    "91": "Île-de-France",
    "92": "Île-de-France",
    "93": "Île-de-France",
    "94": "Île-de-France",
    "95": "Île-de-France",
    "14": "Normandie",
    "27": "Normandie",
    "50": "Normandie",
    "61": "Normandie",
    "76": "Normandie",
    "16": "Nouvelle-Aquitaine",
    "17": "Nouvelle-Aquitaine",
    "19": "Nouvelle-Aquitaine",
    "23": "Nouvelle-Aquitaine",
    "24": "Nouvelle-Aquitaine",
    "33": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine",
    "47": "Nouvelle-Aquitaine",
    "64": "Nouvelle-Aquitaine",
    "79": "Nouvelle-Aquitaine",
    "86": "Nouvelle-Aquitaine",
    "87": "Nouvelle-Aquitaine",
    "09": "Occitanie",
    "11": "Occitanie",
    "12": "Occitanie",
    "30": "Occitanie",
    "31": "Occitanie",
    "32": "Occitanie",
    "34": "Occitanie",
    "46": "Occitanie",
    "48": "Occitanie",
    "65": "Occitanie",
    "66": "Occitanie",
    "81": "Occitanie",
    "82": "Occitanie",
    "44": "Pays de la Loire",
    "49": "Pays de la Loire",
    "53": "Pays de la Loire",
    "72": "Pays de la Loire",
    "85": "Pays de la Loire",
    "04": "Provence-Alpes-Côte d'Azur",
    "05": "Provence-Alpes-Côte d'Azur",
    "06": "Provence-Alpes-Côte d'Azur",
    "13": "Provence-Alpes-Côte d'Azur",
    "83": "Provence-Alpes-Côte d'Azur",
    "84": "Provence-Alpes-Côte d'Azur",
    "2A": "Corse",
    "2B": "Corse",
}


class PagesJaunesScraper(BaseScraper):
    source_name = "pages_jaunes"

    def __init__(self):
        self.browser = None
        self.context = None
        self.playwright = None

    async def _init_browser(self):
        if not self.playwright:
            launch_kwargs = {"headless": True}
            proxy_config = proxy_pool.next_playwright_proxy()
            if proxy_config:
                launch_kwargs["proxy"] = proxy_config
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(**launch_kwargs)
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="fr-FR",
                timezone_id="Europe/Paris",
                user_agent=pick_user_agent(),
            )

    async def search(
        self,
        keywords: list[str],
        city: str | None = None,
        radius_km: int | None = None,
        max_results: int = 100,
    ) -> list[ScrapedLead]:
        await self._init_browser()
        leads: list[ScrapedLead] = []

        query = " ".join(keywords)
        where = city or "France"

        page = await self.context.new_page()
        await apply_stealth(page)

        try:
            # Navigate to Pages Jaunes search
            search_url = f"https://www.pagesjaunes.fr/annuaire/chercherlespros?quoiqui={quote_plus(query)}&ou={quote_plus(where)}"
            await run_with_retries(
                "pages_jaunes.goto",
                lambda: page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=max(30000, int(settings.request_delay_seconds * 1000) * 30),
                ),
            )
            await jitter_sleep(2.0, 3.2)

            # Handle cookie consent
            try:
                consent = page.locator("#didomi-notice-agree-button")
                if await consent.count() > 0:
                    await consent.click()
                    await jitter_sleep(0.6, 1.3)
            except Exception:
                pass

            page_num = 1
            max_pages = (max_results // 20) + 1  # ~20 results per page

            while len(leads) < max_results and page_num <= max_pages:
                # Extract results from current page
                result_items = page.locator(".bi-bloc")
                count = await result_items.count()

                if count == 0:
                    # Try alternative selector
                    result_items = page.locator('[id^="bi-"]')
                    count = await result_items.count()

                if count == 0:
                    logger.info(f"No results found on page {page_num}")
                    break

                for i in range(min(count, max_results - len(leads))):
                    try:
                        lead = await self._extract_lead_from_card(result_items.nth(i))
                        if lead:
                            leads.append(lead)
                        await jitter_sleep(0.15, 0.45)
                    except Exception as e:
                        logger.debug(f"Failed to extract PJ lead {i}: {e}")
                        continue

                # Go to next page
                page_num += 1
                next_btn = page.locator("#pagination-next, a.link_pagination.next")
                if await next_btn.count() > 0 and len(leads) < max_results:
                    try:
                        await run_with_retries(
                            "pages_jaunes.next_page",
                            lambda: next_btn.first.click(timeout=10000),
                            retries=2,
                        )
                        await jitter_sleep(2.0, 3.0)
                    except Exception:
                        break
                else:
                    break

        except Exception as e:
            logger.error(f"Pages Jaunes search failed: {e}")
        finally:
            await page.close()

        return leads

    async def _extract_lead_from_card(self, card) -> ScrapedLead | None:
        """Extract lead data from a Pages Jaunes result card."""
        try:
            # Company name
            name_el = card.locator(
                ".denomination-links h3, .bi-denomination a, .company_name"
            )
            if await name_el.count() == 0:
                return None
            name = (await name_el.first.text_content() or "").strip()
            if not name:
                return None

            lead = ScrapedLead(company_name=name)

            # Source URL
            link_el = card.locator(".denomination-links a, .bi-denomination a")
            if await link_el.count() > 0:
                href = await link_el.first.get_attribute("href")
                if href:
                    lead.source_url = (
                        f"https://www.pagesjaunes.fr{href}"
                        if href.startswith("/")
                        else href
                    )

            # Category/sector
            sector_el = card.locator(".bi-activity-type, .activite, .bi-categorie")
            if await sector_el.count() > 0:
                lead.sector = (await sector_el.first.text_content() or "").strip()

            # Address
            addr_el = card.locator(
                ".bi-address .bi-address-street, .address-container .street-address, .bi-adresse"
            )
            if await addr_el.count() > 0:
                lead.address = (await addr_el.first.text_content() or "").strip()

            # City + postal code
            locality_el = card.locator(
                ".bi-address .bi-address-city, .address-container .locality, .bi-localite"
            )
            if await locality_el.count() > 0:
                locality_text = (await locality_el.first.text_content() or "").strip()
                # Format: "75001 Paris" or "Paris (75001)"
                match = re.search(r"(\d{5})\s*(.+)", locality_text)
                if match:
                    lead.postal_code = match.group(1)
                    lead.city = match.group(2).strip()
                    lead.department = lead.postal_code[:2]
                    lead.region = DEPT_TO_REGION.get(lead.department, "")
                else:
                    match2 = re.search(r"(.+?)\s*\((\d{5})\)", locality_text)
                    if match2:
                        lead.city = match2.group(1).strip()
                        lead.postal_code = match2.group(2)
                        lead.department = lead.postal_code[:2]
                        lead.region = DEPT_TO_REGION.get(lead.department, "")
                    else:
                        lead.city = locality_text

            # Phone
            phone_el = card.locator(
                ".bi-phone .coord-et-numero .tel, .clickable_phone_number, .bi-phone-number"
            )
            if await phone_el.count() > 0:
                phone_text = (await phone_el.first.text_content() or "").strip()
                if phone_text and len(re.sub(r"\s", "", phone_text)) >= 10:
                    lead.phones = [phone_text]
            else:
                # Try broader phone search
                card_html = await card.inner_html()
                phones = extract_phones(card_html)
                if phones:
                    lead.phones = phones[:2]

            # Website
            website_el = card.locator(
                'a.pj-link--website, a[data-pjlabel="site_internet"], a.bi-website'
            )
            if await website_el.count() > 0:
                website_href = await website_el.first.get_attribute("href")
                if website_href:
                    lead.website = website_href

            # Emails from card HTML
            card_html = await card.inner_html()
            emails = extract_emails(card_html)
            if emails:
                lead.emails = emails[:3]

            return lead

        except Exception as e:
            logger.debug(f"PJ card extraction failed: {e}")
            return None

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
