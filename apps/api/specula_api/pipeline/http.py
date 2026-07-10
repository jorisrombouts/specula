"""Polite HTTP fetching: robots.txt, per-domain rate limiting, retry/backoff."""

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import BaseModel

from specula_api.config import Settings

_MAX_ATTEMPTS = 3
_RETRYABLE_STATUSES = {429}


class FetchedDoc(BaseModel):
    url: str
    status: int
    text: str
    content_type: str | None = None


class Disallowed(Exception):
    """Raised when robots.txt disallows fetching a URL."""


class Fetcher(Protocol):
    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc: ...
    async def aclose(self) -> None: ...


class PoliteFetcher:
    """Honors robots.txt, per-domain delay, and retries 429/5xx with backoff."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            headers={"User-Agent": settings.crawl_user_agent},
            timeout=settings.crawl_timeout_s,
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_hit_monotonic: dict[str, float] = {}

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        parts = urlsplit(url)
        host = parts.netloc
        robots = await self._robots_for(host, parts.scheme or "https")
        if not robots.can_fetch(self._settings.crawl_user_agent, url):
            raise Disallowed(url)

        await self._throttle(host)
        response = await self._get_with_retry(url, accept)
        return FetchedDoc(
            url=str(response.url),
            status=response.status_code,
            text=response.text,
            content_type=response.headers.get("content-type"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _robots_for(self, host: str, scheme: str) -> RobotFileParser:
        lock = self._robots_locks.setdefault(host, asyncio.Lock())
        async with lock:
            cached = self._robots.get(host)
            if cached is not None:
                return cached
            robots = RobotFileParser()
            try:
                response = await self._client.get(f"{scheme}://{host}/robots.txt")
                if response.status_code >= 400:
                    robots.parse([])
                else:
                    robots.parse(response.text.splitlines())
            except httpx.HTTPError:
                # Fail open: robots.txt unavailable is not the same as disallowed.
                robots.parse([])
            self._robots[host] = robots
            return robots

    async def _throttle(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            delay_s = self._settings.crawl_per_domain_delay_ms / 1000
            last = self._last_hit_monotonic.get(host)
            if last is not None:
                wait = delay_s - (time.monotonic() - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_hit_monotonic[host] = time.monotonic()

    async def _get_with_retry(self, url: str, accept: str) -> httpx.Response:
        attempt = 1
        while True:
            response = await self._client.get(url, headers={"Accept": accept})
            retryable = response.status_code in _RETRYABLE_STATUSES or response.status_code >= 500
            if not retryable or attempt >= _MAX_ATTEMPTS:
                return response
            await asyncio.sleep(_retry_delay(response, attempt))
            attempt += 1


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return 0.5 * (2.0 ** (attempt - 1))


class RecordedFetcher:
    """Reads recorded responses from <fixtures_dir>/http/<sha256(url)>.json. No network."""

    def __init__(self, fixtures_dir: str | Path) -> None:
        self._dir = Path(fixtures_dir) / "http"

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        path = self._dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"
        if not path.exists():
            return FetchedDoc(url=url, status=404, text="")
        data = json.loads(path.read_text())
        return FetchedDoc.model_validate(data)

    async def aclose(self) -> None:
        return None
