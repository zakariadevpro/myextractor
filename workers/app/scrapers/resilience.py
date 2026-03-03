import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def pick_user_agent() -> str:
    return random.choice(USER_AGENTS)


async def jitter_sleep(min_seconds: float = 0.25, max_seconds: float = 1.0) -> None:
    if max_seconds <= 0:
        return
    minimum = max(0.0, min_seconds)
    maximum = max(minimum, max_seconds)
    await asyncio.sleep(random.uniform(minimum, maximum))


async def run_with_retries(
    operation: str,
    coro_factory: Callable[[], Awaitable[T]],
    *,
    retries: int | None = None,
    base_delay_seconds: float | None = None,
    max_delay_seconds: float = 8.0,
) -> T:
    attempts = max(1, retries if retries is not None else settings.max_retries)
    base_delay = max(0.2, base_delay_seconds if base_delay_seconds is not None else settings.request_delay_seconds)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break

            # Exponential backoff + jitter helps avoid bursty retry patterns.
            delay = min(max_delay_seconds, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0.0, 0.5)
            logger.warning(
                "%s failed (attempt %s/%s): %s. Retrying in %.2fs",
                operation,
                attempt,
                attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc
