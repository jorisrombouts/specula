"""Polite HTTP fetching: robots.txt, per-domain rate limiting, retry/backoff."""

import asyncio
import hashlib
import ipaddress
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

# Longer than this and we stop waiting: the crawl runs inside a FastAPI BackgroundTask that
# holds an open tenant_session, so honouring a `Retry-After: 86400` would pin a DB connection
# for a day. We surface the 429 instead, which adapters turn into BoardUnavailable.
MAX_RETRY_AFTER_S = 30.0

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_NON_PUBLIC_HOST_SUFFIXES = (".localhost", ".internal", ".local")


class FetchedDoc(BaseModel):
    url: str
    status: int
    text: str
    content_type: str | None = None


class Disallowed(Exception):
    """Raised when a URL must not be fetched — robots.txt, or a blocked target."""


class BlockedTarget(Disallowed):
    """The URL is not a public http(s) endpoint.

    A posting's `source_url` comes from third-party ATS JSON or a scraped `href` and is later
    re-fetched, so it is untrusted input to the fetcher: without this, a feed could point us
    at `http://169.254.169.254/...` and the response body would be sent to the LLM and stored.
    Subclasses `Disallowed` so every adapter's existing handling applies unchanged.

    Scope: scheme, IP literals and obvious local names. A hostname that *resolves* to a
    private address is not caught — that would need a DNS lookup on every fetch.
    """


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
        _assert_fetchable(url)
        parts = urlsplit(url)
        host = parts.netloc
        robots = await self._robots_for(host, parts.scheme or "https")
        if not robots.can_fetch(self._settings.crawl_user_agent, url):
            raise Disallowed(url)

        await self._throttle(host)
        try:
            response = await self._get_with_retry(url, accept)
        except httpx.HTTPError:
            # Dead host, DNS failure, timeout, connection reset — a crawler skips a
            # bad URL, it never crashes the run. Downstream treats non-200 as "no page".
            return FetchedDoc(url=url, status=0, text="")
        # The client follows redirects, so re-check where we actually landed: a 302 must not
        # be able to launder the fetch onto a target the guard just refused.
        _assert_fetchable(str(response.url))
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
            delay = _retry_delay(response, attempt)
            if delay is None:
                return response  # asked to wait longer than we're willing to hold the run
            await asyncio.sleep(delay)
            attempt += 1


def _assert_fetchable(url: str) -> None:
    """Refuse anything that isn't a public http(s) endpoint. See `BlockedTarget`."""
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise BlockedTarget(f"refusing {url!r}: scheme {parts.scheme!r} is not http(s)")
    hostname = parts.hostname
    if not hostname:
        raise BlockedTarget(f"refusing {url!r}: no host")
    lowered = hostname.lower()
    if lowered == "localhost" or lowered.endswith(_NON_PUBLIC_HOST_SUFFIXES):
        raise BlockedTarget(f"refusing {url!r}: non-public host {hostname!r}")
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return  # a name, not a literal — not resolved here (see BlockedTarget's docstring)
    if not address.is_global or address.is_multicast:
        raise BlockedTarget(f"refusing {url!r}: non-public address {address}")


def _retry_delay(response: httpx.Response, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None to stop retrying altogether."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            requested = float(retry_after)
        except ValueError:
            pass  # an HTTP-date rather than seconds — fall back to exponential backoff
        else:
            return requested if requested <= MAX_RETRY_AFTER_S else None
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


class RecordingFetcher:
    """Wraps a live `Fetcher` and writes every response to
    `<fixtures_dir>/http/<sha256(url)>.json`, the exact key scheme `RecordedFetcher` reads from.
    Used by pipeline_mode="record" so a live run regenerates the committed fixtures for a later
    "recorded" run/CI to replay deterministically. A `Disallowed` raise from the live fetcher
    propagates unrecorded — there's no response to save, and that's consistent with a replay
    miss (RecordedFetcher returns a synthetic 404 rather than raising)."""

    def __init__(self, live: Fetcher, fixtures_dir: str | Path) -> None:
        self._live = live
        self._dir = Path(fixtures_dir) / "http"

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        doc = await self._live.get(url, accept=accept)
        path = self._dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc.model_dump(), indent=2) + "\n")
        return doc

    async def aclose(self) -> None:
        await self._live.aclose()
