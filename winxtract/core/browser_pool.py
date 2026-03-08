import asyncio
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import Browser, Page, Playwright, async_playwright

from winxtract.core.rate_limit import DomainRateLimiter
from winxtract.core.robots import RobotsCache


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


class BrowserPool:
    def __init__(
        self,
        *,
        headless: bool,
        max_pages: int,
        timeout_ms: int,
        min_domain_delay: float,
        max_retries: int = 3,
        backoff_min: float = 1.0,
        backoff_max: float = 10.0,
        user_agents: list[str] | None = None,
        proxy_url: str | None = None,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self.backoff_min = backoff_min
        self.backoff_max = backoff_max
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.proxy_url = (proxy_url or "").strip() or None
        self._semaphore = asyncio.Semaphore(max_pages)
        self._rate_limiter = DomainRateLimiter(min_domain_delay)
        self._robots = RobotsCache()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        launch_kwargs = {"headless": self.headless}
        if self.proxy_url:
            launch_kwargs["proxy"] = {"server": self.proxy_url}
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    @asynccontextmanager
    async def open_page(self, url: str, *, respect_robots: bool = True) -> AsyncIterator[Page]:
        if self._browser is None:
            raise RuntimeError("BrowserPool not started")
        if respect_robots and not await self._robots.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")

        await self._semaphore.acquire()
        try:
            await self._rate_limiter.wait_for(url)
            context = await self._browser.new_context(
                user_agent=random.choice(self.user_agents),
            )
            page = await context.new_page()
            page.set_default_timeout(self.timeout_ms)
            await self._goto_with_retry(page, url)
            yield page
            await context.close()
        finally:
            self._semaphore.release()

    async def _goto_with_retry(self, page: Page, url: str) -> None:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
                status = response.status if response else None
                if status in {403, 429, 503}:
                    if attempt == self.max_retries:
                        raise PermissionError(f"Access blocked with HTTP {status} for {url}")
                    wait_time = min(self.backoff_max, self.backoff_min * (2 ** (attempt - 1)))
                    await asyncio.sleep(wait_time)
                    continue
                return
            except Exception:
                if attempt == self.max_retries:
                    raise
                wait_time = min(self.backoff_max, self.backoff_min * (2 ** (attempt - 1)))
                await asyncio.sleep(wait_time)
