import threading
from urllib.parse import unquote, urlparse

from app.config import settings


def _parse_proxy_urls(raw: str) -> list[str]:
    if not raw:
        return []
    chunks = raw.replace("\n", ",").replace(";", ",").split(",")
    cleaned = [item.strip() for item in chunks if item.strip()]
    return cleaned


class ProxyPool:
    def __init__(self, urls: list[str], enabled: bool):
        self._urls = urls
        self._enabled = enabled and bool(urls)
        self._index = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def next_proxy_url(self) -> str | None:
        if not self._enabled or not self._urls:
            return None
        with self._lock:
            value = self._urls[self._index % len(self._urls)]
            self._index += 1
            return value

    def next_playwright_proxy(self) -> dict | None:
        proxy_url = self.next_proxy_url()
        if not proxy_url:
            return None

        parsed = urlparse(proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server = f"{server}:{parsed.port}"
        proxy: dict[str, str] = {"server": server}
        if parsed.username:
            proxy["username"] = unquote(parsed.username)
        if parsed.password:
            proxy["password"] = unquote(parsed.password)
        return proxy


proxy_pool = ProxyPool(
    urls=_parse_proxy_urls(settings.proxy_pool_urls),
    enabled=settings.proxy_rotation_enabled,
)
