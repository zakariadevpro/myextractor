import asyncio
import logging

from playwright.async_api import Browser, BrowserContext, async_playwright

from app.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages a pool of Playwright browser contexts."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_browsers)

    async def start(self):
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            logger.info("Browser pool started")

    async def get_context(self) -> BrowserContext:
        """Get a new browser context (isolated session)."""
        await self._semaphore.acquire()
        if not self._browser:
            await self.start()
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        return context

    def release(self):
        """Release a browser context slot."""
        self._semaphore.release()

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser pool closed")


# Singleton instance
browser_manager = BrowserManager()
