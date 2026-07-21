"""ATS source-adapter seam: turn a company's careers presence into RawPostings."""

import json
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree.ElementTree import Element

from pydantic import BaseModel
from selectolax.parser import HTMLParser

from specula_api.pipeline.content_hash import content_hash
from specula_api.pipeline.http import Disallowed, Fetcher

# Hosts discovery's web-search is restricted to. SmartRecruiters is deliberately NOT here:
# `api.smartrecruiters.com/robots.txt` allows only LinkedInBot on `/v1/companies/` and
# disallows everyone else, so our polite fetcher (correctly) refuses it and the adapter can
# never return postings. Surfacing those companies would burn discovery slots on candidates
# we can't ingest. `SmartRecruitersAdapter` is kept, ready to re-enable if official API
# access is arranged — we do not work around robots.txt.
ATS_ALLOWED_DOMAINS = (
    "boards.greenhouse.io",
    "greenhouse.io",
    "jobs.lever.co",
    "lever.co",
    "jobs.ashbyhq.com",
    "ashbyhq.com",
    "recruitee.com",
    "apply.workable.com",
    "workable.com",
    "jobs.personio.de",
    "jobs.personio.com",
    "personio.de",
)

_GREENHOUSE_HOSTS = ("boards.greenhouse.io", "greenhouse.io")
_LEVER_HOSTS = ("jobs.lever.co", "lever.co")
_ASHBY_HOSTS = ("jobs.ashbyhq.com", "ashbyhq.com")
_SMARTRECRUITERS_HOSTS = ("jobs.smartrecruiters.com", "smartrecruiters.com")
_RECRUITEE_HOSTS = ("recruitee.com",)
_WORKABLE_HOSTS = ("apply.workable.com", "workable.com")
_PERSONIO_HOSTS = ("jobs.personio.de", "jobs.personio.com", "personio.de")
_JOB_LINK_KEYWORDS = ("job", "career", "position", "opening")


class BoardUnavailable(Exception):
    """The board could not be READ — robots-disallowed, non-200 (including PoliteFetcher's
    status=0 transport sentinel), or an unparseable body.

    Distinct from a board that was read and lists nothing: `list_postings` returning `[]`
    tells `fetch_postings` every posting is gone and retires them all, so a failed fetch must
    never masquerade as an empty one.
    """


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
    if hint in (
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "recruitee",
        "workable",
        "personio",
    ):
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
        if _matches_host(host, _SMARTRECRUITERS_HOSTS):
            return "smartrecruiters"
        if _matches_host(host, _RECRUITEE_HOSTS):
            return "recruitee"
        if _matches_host(host, _WORKABLE_HOSTS):
            return "workable"
        if _matches_host(host, _PERSONIO_HOSTS):
            return "personio"
    return None


def resolve_adapter(company: CompanyLike) -> SourceAdapter:
    ats = detect_ats(domain=company.domain, careers_url=company.careers_url, ats_hint=company.ats)
    if ats == "greenhouse":
        return GreenhouseAdapter()
    if ats == "lever":
        return LeverAdapter()
    if ats == "ashby":
        return AshbyAdapter()
    if ats == "smartrecruiters":
        return SmartRecruitersAdapter()
    if ats == "recruitee":
        return RecruiteeAdapter()
    if ats == "workable":
        return WorkableAdapter()
    if ats == "personio":
        return PersonioAdapter()
    return GenericHtmlAdapter()


def _host_of(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value if "://" in value else f"//{value}")
    return parts.netloc.lower() or None


def _matches_host(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)


def _board_token(company: CompanyLike, hosts: tuple[str, ...]) -> str | None:
    """Derive the ATS board token from careers_url (preferred), else the domain.

    The domain may only supply a token when it IS on the ATS host. A bare domain label was
    previously used verbatim, so an LLM-guessed `ats` (enrich feeds it into detect_ats, which
    trusts it) turned monday.com into apply.workable.com/.../monday — ingesting whichever
    stranger owns that slug as this company.
    """
    careers_url = company.careers_url
    if careers_url:
        parts = urlsplit(careers_url if "://" in careers_url else f"//{careers_url}")
        host = parts.netloc.lower()
        if _matches_host(host, hosts):
            segment = next((s for s in parts.path.split("/") if s), None)
            if segment:
                return segment.lower()
            label = _leading_label_on_host(host, hosts)
            if label:
                return label

    return _leading_label_on_host(company.domain, hosts)


def _leading_label_on_host(value: str | None, hosts: tuple[str, ...]) -> str | None:
    """The per-tenant label of a host that is itself on the ATS
    (acme.job-boards.greenhouse.io -> "acme"); None for anything not on the ATS host.

    Load-bearing for live discovery: those approvals carry a fabricated ATS-host domain and
    no careers_url, so this is the only place their token comes from.
    """
    if not value:
        return None
    host = value.lower().removeprefix("www.")
    if "://" in host:
        host = urlsplit(host).netloc
    for suffix in hosts:
        if host.endswith(f".{suffix}"):
            label = host[: -(len(suffix) + 1)].split(".")[0]
            if label:
                return label
    return None


def _subdomain_token(company: CompanyLike, hosts: tuple[str, ...]) -> str | None:
    """Token for ATSes where it lives in the subdomain rather than the URL path (Recruitee,
    Personio). Host-verified for the same reason as `_board_token`."""
    return _leading_label_on_host(company.careers_url, hosts) or _leading_label_on_host(
        company.domain, hosts
    )


async def _fetch_json(fetcher: Fetcher, url: str) -> object:
    try:
        doc = await fetcher.get(url, accept="application/json")
    except Disallowed as exc:
        raise BoardUnavailable(f"robots.txt disallows {url}") from exc
    if doc.status != 200 or not doc.text:
        raise BoardUnavailable(f"{url} returned status {doc.status}")
    try:
        data: object = json.loads(doc.text)
    except json.JSONDecodeError as exc:
        raise BoardUnavailable(f"{url} returned unparseable JSON") from exc
    return data


async def _fetch_xml(fetcher: Fetcher, url: str) -> Element:
    try:
        doc = await fetcher.get(url, accept="application/xml")
    except Disallowed as exc:
        raise BoardUnavailable(f"robots.txt disallows {url}") from exc
    if doc.status != 200 or not doc.text:
        raise BoardUnavailable(f"{url} returned status {doc.status}")
    try:
        return ElementTree.fromstring(doc.text)
    except ElementTree.ParseError as exc:
        raise BoardUnavailable(f"{url} returned unparseable XML") from exc


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
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
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
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
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
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
        data = await _fetch_json(fetcher, f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        return _raw_postings(
            (job.get("jobUrl") or job.get("applyUrl"), job.get("id"), job.get("title"))
            for job in jobs
            if isinstance(job, dict)
        )


class SmartRecruitersAdapter:
    ats = "smartrecruiters"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _board_token(company, _SMARTRECRUITERS_HOSTS)
        if not token:
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
        data = await _fetch_json(
            fetcher, f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
        )
        jobs = data.get("content") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        return _raw_postings(
            (_smartrecruiters_url(job), job.get("id"), job.get("name"))
            for job in jobs
            if isinstance(job, dict)
        )


class RecruiteeAdapter:
    ats = "recruitee"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _subdomain_token(company, _RECRUITEE_HOSTS)
        if not token:
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
        data = await _fetch_json(fetcher, f"https://{token}.recruitee.com/api/offers/")
        offers = data.get("offers") if isinstance(data, dict) else None
        if not isinstance(offers, list):
            return []
        return _raw_postings(
            (offer.get("careers_url"), offer.get("id"), offer.get("title"))
            for offer in offers
            if isinstance(offer, dict)
        )


class WorkableAdapter:
    ats = "workable"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _board_token(company, _WORKABLE_HOSTS)
        if not token:
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
        data = await _fetch_json(
            fetcher, f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"
        )
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        return _raw_postings(
            (job.get("url"), job.get("shortcode"), job.get("title"))
            for job in jobs
            if isinstance(job, dict)
        )


class PersonioAdapter:
    ats = "personio"

    async def list_postings(self, company: CompanyLike, fetcher: Fetcher) -> list[RawPosting]:
        token = _subdomain_token(company, _PERSONIO_HOSTS)
        if not token:
            raise BoardUnavailable(
                f"no {self.ats} board token derivable for {company.domain or company.careers_url!r}"
            )
        root = await _fetch_xml(fetcher, f"https://{token}.jobs.personio.de/xml")
        if root is None:
            return []
        return _raw_postings(_personio_rows(root, token))


def _smartrecruiters_url(job: dict[str, object]) -> str | None:
    company = job.get("company")
    identifier = company.get("identifier") if isinstance(company, dict) else None
    job_id = job.get("id")
    if not isinstance(identifier, str) or not identifier or job_id is None:
        return None
    return f"https://jobs.smartrecruiters.com/{identifier}/{job_id}"


def _personio_rows(root: Element, token: str) -> Iterable[tuple[object, object, object]]:
    for position in root.findall("position"):
        job_id = position.findtext("id")
        if not job_id:
            continue
        yield f"https://{token}.jobs.personio.de/job/{job_id}", job_id, position.findtext("name")


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
            raise BoardUnavailable(f"no careers_url to scrape for {company.domain!r}")
        try:
            doc = await fetcher.get(careers_url, accept="text/html")
        except Disallowed as exc:
            raise BoardUnavailable(f"robots.txt disallows {careers_url}") from exc
        if doc.status != 200 or not doc.text:
            raise BoardUnavailable(f"{careers_url} returned status {doc.status}")

        tree = HTMLParser(doc.text)
        postings: list[RawPosting] = []
        seen_urls: set[str] = set()
        for anchor in tree.css("a[href]"):
            href = anchor.attributes.get("href")
            if not href:
                continue
            url = _canonical_job_url(urljoin(careers_url, href))
            if url in seen_urls or not _looks_like_job_link(url, careers_url):
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


def _looks_like_job_link(url: str, base_url: str) -> bool:
    """Whether an <a href> off a careers page plausibly points at one posting.

    Without the scheme/host checks, `mailto:`, `javascript:`, in-page `#anchors` and
    third-party links (a LinkedIn jobs page) all became Posting rows: each one is then fetched
    and LLM-extracted, consuming the per-company extraction budget ahead of real jobs.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.netloc.lower()
    base = urlsplit(base_url)
    on_ats = any(host == d or host.endswith(f".{d}") for d in ATS_ALLOWED_DOMAINS)
    if not on_ats and host != base.netloc.lower():
        return False
    path = parts.path.rstrip("/")
    if not path.strip("/"):
        return False
    if host == base.netloc.lower() and path == base.path.rstrip("/"):
        return False  # the careers page linking to itself
    return True if on_ats else any(k in path.lower() for k in _JOB_LINK_KEYWORDS)


def _canonical_job_url(url: str) -> str:
    """Drop the fragment and tracking params so one job doesn't become several postings.
    Meaningful params (gh_jid, lever ids) are preserved — only known trackers go."""
    parts = urlsplit(url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"gh_src", "ref", "source"}
    ]
    return urlunsplit(parts._replace(query=urlencode(kept), fragment=""))


def _raw_postings(rows: Iterable[tuple[object, object, object]]) -> list[RawPosting]:
    return [p for url, job_id, title in rows if (p := _to_raw_posting(url, job_id, title))]
