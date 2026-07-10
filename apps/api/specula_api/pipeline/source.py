"""ATS source-adapter seam: turn a company's careers presence into RawPostings."""

import json
from collections.abc import Iterable
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel
from selectolax.parser import HTMLParser

from specula_api.pipeline.content_hash import content_hash
from specula_api.pipeline.http import Disallowed, Fetcher

ATS_ALLOWED_DOMAINS = (
    "boards.greenhouse.io",
    "greenhouse.io",
    "jobs.lever.co",
    "lever.co",
    "jobs.ashbyhq.com",
    "ashbyhq.com",
)

_GREENHOUSE_HOSTS = ("boards.greenhouse.io", "greenhouse.io")
_LEVER_HOSTS = ("jobs.lever.co", "lever.co")
_ASHBY_HOSTS = ("jobs.ashbyhq.com", "ashbyhq.com")
_JOB_LINK_KEYWORDS = ("job", "career", "position", "opening")


class RawPosting(BaseModel):
    source_url: str
    external_id: str | None = None
    title_hint: str | None = None
    content_hash: str


class CompanyLike(Protocol):
    domain: str | None
    careers_url: str | None
    ats: str | None


class SourceAdapter(Protocol):
    ats: str

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]: ...


def detect_ats(*, domain: str | None, careers_url: str | None, ats_hint: str | None) -> str | None:
    hint = (ats_hint or "").strip().lower()
    if hint in ("greenhouse", "lever", "ashby"):
        return hint

    for value in (careers_url, domain):
        host = _host_of(value)
        if host is None:
            continue
        if _matches_host(host, _GREENHOUSE_HOSTS):
            return "greenhouse"
        if _matches_host(host, _LEVER_HOSTS):
            return "lever"
        if _matches_host(host, _ASHBY_HOSTS):
            return "ashby"
    return None


def resolve_adapter(company: CompanyLike) -> SourceAdapter:
    ats = detect_ats(domain=company.domain, careers_url=company.careers_url, ats_hint=company.ats)
    if ats == "greenhouse":
        return GreenhouseAdapter()
    if ats == "lever":
        return LeverAdapter()
    if ats == "ashby":
        return AshbyAdapter()
    return GenericHtmlAdapter()


def _host_of(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value if "://" in value else f"//{value}")
    return parts.netloc.lower() or None


def _matches_host(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)


def _board_token(company: CompanyLike, hosts: tuple[str, ...]) -> str | None:
    """Derive the ATS board token from careers_url (preferred) or fall back to domain."""
    careers_url = company.careers_url
    if careers_url:
        parts = urlsplit(careers_url if "://" in careers_url else f"//{careers_url}")
        if _matches_host(parts.netloc.lower(), hosts):
            segment = next((s for s in parts.path.split("/") if s), None)
            if segment:
                return segment.lower()

    domain = company.domain
    if domain:
        label = domain.lower().removeprefix("www.").split(".")[0]
        if label:
            return label
    return None


async def _fetch_json(fetcher: Fetcher, url: str) -> object | None:
    try:
        doc = await fetcher.get(url, accept="application/json")
    except Disallowed:
        return None
    if doc.status != 200 or not doc.text:
        return None
    try:
        data: object = json.loads(doc.text)
    except json.JSONDecodeError:
        return None
    return data


def _to_raw_posting(url: object, job_id: object, title: object) -> RawPosting | None:
    if not isinstance(url, str) or not url:
        return None
    external_id = str(job_id) if job_id is not None else None
    title_hint = title if isinstance(title, str) else None
    return RawPosting(
        source_url=url,
        external_id=external_id,
        title_hint=title_hint,
        content_hash=content_hash(source_url=url, external_id=external_id, title_hint=title_hint),
    )


class GreenhouseAdapter:
    ats = "greenhouse"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _board_token(company, _GREENHOUSE_HOSTS)
        if not token:
            return []
        data = await _fetch_json(
            fetcher, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        )
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        return _raw_postings(
            (job.get("absolute_url"), job.get("id"), job.get("title"))
            for job in jobs
            if isinstance(job, dict)
        )


class LeverAdapter:
    ats = "lever"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _board_token(company, _LEVER_HOSTS)
        if not token:
            return []
        data = await _fetch_json(fetcher, f"https://api.lever.co/v0/postings/{token}?mode=json")
        if not isinstance(data, list):
            return []
        return _raw_postings(
            (job.get("hostedUrl"), job.get("id"), job.get("text"))
            for job in data
            if isinstance(job, dict)
        )


class AshbyAdapter:
    ats = "ashby"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _board_token(company, _ASHBY_HOSTS)
        if not token:
            return []
        data = await _fetch_json(fetcher, f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        return _raw_postings(
            (job.get("jobUrl") or job.get("applyUrl"), job.get("id"), job.get("title"))
            for job in jobs
            if isinstance(job, dict)
        )


class GenericHtmlAdapter:
    """Fallback: best-effort scrape of <a> job links off the company's careers page.

    TODO(M3.x): JS-rendered adapter — a board that needs client-side rendering (no
    Playwright dep in this milestone) has no <a> links in the fetched HTML and this
    adapter correctly yields [] for it.
    """

    ats = "generic"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        careers_url = company.careers_url
        if not careers_url:
            return []
        try:
            doc = await fetcher.get(careers_url, accept="text/html")
        except Disallowed:
            return []
        if doc.status != 200 or not doc.text:
            return []

        tree = HTMLParser(doc.text)
        postings: list[RawPosting] = []
        seen_urls: set[str] = set()
        for anchor in tree.css("a[href]"):
            href = anchor.attributes.get("href")
            if not href:
                continue
            url = urljoin(careers_url, href)
            if url in seen_urls or not _looks_like_job_link(url):
                continue
            seen_urls.add(url)
            title_hint = anchor.text(strip=True) or None
            postings.append(
                RawPosting(
                    source_url=url,
                    external_id=None,
                    title_hint=title_hint,
                    content_hash=content_hash(
                        source_url=url, external_id=None, title_hint=title_hint
                    ),
                )
            )
        return postings


def _looks_like_job_link(url: str) -> bool:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if any(host == d or host.endswith(f".{d}") for d in ATS_ALLOWED_DOMAINS):
        return True
    return any(keyword in parts.path.lower() for keyword in _JOB_LINK_KEYWORDS)


def _raw_postings(rows: Iterable[tuple[object, object, object]]) -> list[RawPosting]:
    return [p for url, job_id, title in rows if (p := _to_raw_posting(url, job_id, title))]
