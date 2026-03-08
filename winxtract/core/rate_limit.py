import asyncio
import time
from urllib.parse import urlparse


class DomainRateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._next_allowed: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait_for(self, url: str) -> None:
        domain = urlparse(url).netloc.lower()
        async with self._lock:
            now = time.monotonic()
            allowed_at = self._next_allowed.get(domain, now)
            wait_time = max(0.0, allowed_at - now)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._next_allowed[domain] = time.monotonic() + self.min_interval_seconds
