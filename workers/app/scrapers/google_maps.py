import logging
import re

from playwright.async_api import Page, async_playwright

from app.browser.anti_detect import apply_stealth
from app.config import settings
from app.parsers.contact_parser import extract_emails, extract_phones
from app.scrapers.base import BaseScraper, ScrapedLead
from app.scrapers.proxy_pool import proxy_pool
from app.scrapers.resilience import jitter_sleep, pick_user_agent, run_with_retries

logger = logging.getLogger(__name__)


class GoogleMapsScraper(BaseScraper):
    source_name = "google_maps"

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
        leads = []

        query = " ".join(keywords)
        if city:
            query += f" {city}"

        page = await self.context.new_page()
        await apply_stealth(page)

        try:
            # Navigate to Google Maps
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            await run_with_retries(
                "google_maps.goto",
                lambda: page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=max(30000, int(settings.request_delay_seconds * 1000) * 30),
                ),
            )
            await jitter_sleep(2.0, 3.5)  # Let Maps scripts load and hydrate UI.

            # Accept cookies if dialog appears
            try:
                accept_btn = page.locator('button:has-text("Tout accepter")')
                if await accept_btn.count() > 0:
                    await accept_btn.first.click()
                    await jitter_sleep(0.5, 1.4)
            except Exception:
                pass

            # Scroll results panel to load more
            results_collected = 0
            scroll_attempts = 0
            max_scrolls = max_results // 5  # ~5 results per scroll

            while results_collected < max_results and scroll_attempts < max_scrolls:
                # Find result items
                items = page.locator('[role="feed"] > div > div > a')
                count = await items.count()

                if count <= results_collected and scroll_attempts > 3:
                    break

                results_collected = count

                # Scroll the results panel
                feed = page.locator('[role="feed"]')
                if await feed.count() > 0:
                    await feed.evaluate("el => el.scrollTop = el.scrollHeight")
                    await jitter_sleep(1.0, 1.8)

                scroll_attempts += 1

            # Extract data from each result
            items = page.locator('[role="feed"] > div > div > a')
            total = min(await items.count(), max_results)

            for i in range(total):
                try:
                    lead = await self._extract_lead_from_item(page, items.nth(i))
                    if lead:
                        leads.append(lead)
                    await jitter_sleep(0.2, 0.8)
                except Exception as e:
                    logger.warning(f"Failed to extract lead {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Google Maps search failed: {e}")
        finally:
            await page.close()

        return leads

    async def _extract_lead_from_item(self, page: Page, item) -> ScrapedLead | None:
        """Click on a result item and extract business details."""
        try:
            await run_with_retries(
                "google_maps.item_click",
                lambda: item.click(timeout=10000),
                retries=2,
            )
            await jitter_sleep(1.2, 2.4)

            # Extract business name
            name_el = page.locator("h1.DUwDvf")
            if await name_el.count() == 0:
                return None
            name = await name_el.first.text_content()
            if not name:
                return None

            lead = ScrapedLead(company_name=name.strip(), source_url=page.url)

            # Category/sector
            category_el = page.locator('button[jsaction*="category"]')
            if await category_el.count() > 0:
                lead.sector = (await category_el.first.text_content() or "").strip()

            # Address
            address_el = page.locator('[data-item-id="address"] .fontBodyMedium')
            if await address_el.count() > 0:
                full_address = (await address_el.first.text_content() or "").strip()
                lead.address = full_address
                # Try to extract postal code and city
                match = re.search(r"(\d{5})\s+(.+?)(?:,|$)", full_address)
                if match:
                    lead.postal_code = match.group(1)
                    lead.city = match.group(2).strip()
                    lead.department = lead.postal_code[:2]

            # Phone
            phone_el = page.locator('[data-item-id*="phone"] .fontBodyMedium')
            if await phone_el.count() > 0:
                phone_text = (await phone_el.first.text_content() or "").strip()
                if phone_text:
                    lead.phones = [phone_text]

            # Website
            website_el = page.locator('[data-item-id="authority"] .fontBodyMedium')
            if await website_el.count() > 0:
                lead.website = (await website_el.first.text_content() or "").strip()

            # Try to extract additional emails/phones from page content
            page_content = await page.content()
            extra_emails = extract_emails(page_content)
            extra_phones = extract_phones(page_content)
            if extra_emails:
                lead.emails = list(set(lead.emails + extra_emails))
            if extra_phones and not lead.phones:
                lead.phones = list(set(extra_phones))

            return lead

        except Exception as e:
            logger.debug(f"Item extraction failed: {e}")
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
