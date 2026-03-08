import urllib.robotparser
from urllib.parse import urlparse

import httpx


class RobotsCache:
    def __init__(self) -> None:
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def allowed(self, url: str, user_agent: str = "*") -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._cache.get(base)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = f"{base}/robots.txt"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(robots_url)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    return True
            except Exception:
                return True
            self._cache[base] = parser
        return parser.can_fetch(user_agent, url)
