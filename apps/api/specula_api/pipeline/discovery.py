"""Discovery stage: seed-query the web for ATS-hosted job boards and stage them as approvals."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Approval, Company, DiscoveryQueryStat, Lens, Targeting
from specula_api.observability import get_logger
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.openai_client import Source
from specula_api.pipeline.source import ATS_ALLOWED_DOMAINS, detect_ats
from specula_api.pipeline.util import favicon_url
from specula_api.services.discovery_settings import effective_max_searches

_log = get_logger("pipeline.discovery")


class DiscoverResult(BaseModel):
    found: int = 0
    new: int = 0
    errors: int = 0


@dataclass(frozen=True)
class _Candidate:
    domain: str
    ats: str | None
    careers_url: str
    name: str
    found_query: str


# ATSes that host each company at its own subdomain (bunq.recruitee.com,
# smava.jobs.personio.de) — the host is already company-distinguishing, unlike the shared
# boards.greenhouse.io-style hosts, so folding the job-page path segment ("o", "job") into
# the domain below would be wrong rather than merely redundant.
_SUBDOMAIN_TOKEN_ATS = frozenset({"recruitee", "personio"})

# First path segments that are generic ATS routing words, never a company slug. On a shared
# host (boards.greenhouse.io/embed/…, …/jobs/…) the real company isn't in the URL, and these
# job links just duplicate the company's properly-slugged posting — so a candidate whose only
# identifier is one of these is dropped rather than staged as an "Embed"/"Jobs" card.
_GENERIC_PATH_SEGMENTS = frozenset(
    {
        "view",
        "embed",
        "jobs",
        "job",
        "careers",
        "career",
        "apply",
        "search",
        "position",
        "positions",
    }
)


def _region_hint(lens: Lens) -> str:
    """A short location hint for a job-search query, from the lens scope (a country code
    or 'City, CC') or, failing that, a remote/EU cue in the lens name. Generic lenses
    ('All', 'Foreign HQ') contribute no hint. 'Any region' is not a search term."""
    scope = (lens.scope or "").strip()
    if scope and scope.lower() != "any region":
        return {"ES": "Spain", "DE": "Germany", "NL": "Netherlands"}.get(
            scope, scope.split(",")[0].strip()
        )
    name = (lens.name or "").lower()
    if "remote" in name or "eu" in name:
        return "remote EU"
    return ""


@dataclass(frozen=True)
class SeedQuery:
    text: str
    exhaustible: bool  # False for user lens seeds (always run); True for generated role queries


def build_seed_queries(role_titles: list[str], lenses: list[Lens], *, cap: int) -> list[SeedQuery]:
    """Effective ATS job-board searches, deduped and capped at `cap`. Each active lens's own
    seeds run FIRST, verbatim (user-crafted, high-signal, never parked by the exhaustion cache).
    Then ONE combined role query per active lens — the role titles are near-synonyms, so a single
    search per lens finds the same companies as one-per-title at a fraction of the cost. The
    web_search tool is domain-filtered to ATS hosts, so a query only needs the roles + a location
    cue, not a pile of synonyms."""
    active = [lens for lens in lenses if lens.active]
    out: list[SeedQuery] = []
    seen: set[str] = set()

    def _add(text: str, *, exhaustible: bool) -> bool:
        """Append a deduped, non-empty query; return True once the cap is full."""
        text = text.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(SeedQuery(text, exhaustible))
        return len(out) >= cap

    for lens in active:
        for seed in lens.seeds:
            if _add(seed, exhaustible=False):
                return out
    roles = " / ".join(r.strip() for r in role_titles if r.strip())
    if roles:
        for lens in active:
            combined = " ".join(p for p in (roles, "jobs", _region_hint(lens)) if p)
            if _add(combined, exhaustible=True):
                return out
    return out


# Exhaustion cache: a query that finds 0 new companies this many runs in a row is "played out"
# and parked for the cooldown before it's retried once (new postings appear over time).
_EXHAUSTION_THRESHOLD = 2
_COOLDOWN = timedelta(days=7)


async def _exhausted_queries(session: AsyncSession, user_id: UUID, now: datetime) -> set[str]:
    """Query texts to skip this run: emptied out (>= threshold) and still inside the cooldown."""
    rows = await session.scalars(
        select(DiscoveryQueryStat).where(DiscoveryQueryStat.user_id == user_id)
    )
    return {
        r.query
        for r in rows
        if r.consecutive_empty_runs >= _EXHAUSTION_THRESHOLD and now - r.last_run_at < _COOLDOWN
    }


async def _record_query_stats(
    session: AsyncSession, user_id: UUID, new_by_query: dict[str, int], now: datetime
) -> None:
    """Update each executed query's exhaustion memory: reset its empty-streak when it found new
    companies, else extend it."""
    for query, new_count in new_by_query.items():
        stat = await session.get(DiscoveryQueryStat, (user_id, query))
        if stat is None:
            stat = DiscoveryQueryStat(user_id=user_id, query=query)
            session.add(stat)
            prev_empty = 0
        else:
            prev_empty = stat.consecutive_empty_runs
        stat.last_run_at = now
        stat.consecutive_empty_runs = 0 if new_count > 0 else prev_empty + 1


async def discover(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> DiscoverResult:
    targeting = await session.get(Targeting, user_id)
    role_titles = targeting.role_titles if targeting is not None else []

    lenses = list((await session.scalars(select(Lens).where(Lens.user_id == user_id))).all())
    cap = await effective_max_searches(session, user_id, deps.settings)
    queries = build_seed_queries(role_titles, lenses, cap=cap)
    _log.info("pipeline.stage", extra={"stage": "discovery", "queries": len(queries)})
    if not queries:
        return DiscoverResult()

    existing_domains = await _existing_domains(session, user_id)
    skip = await _exhausted_queries(session, user_id, deps.now())

    found = 0
    staged: list[_Candidate] = []
    new = 0
    errors = 0
    new_by_query: dict[str, int] = {}
    for seed_query in queries:
        query = seed_query.text
        # A played-out auto-role query (all its companies already known) is parked until its
        # cooldown lapses; user seeds always run.
        if seed_query.exhaustible and query in skip:
            continue
        try:
            sources = await deps.openai.discover_sources(
                [query], allowed_domains=ATS_ALLOWED_DOMAINS
            )
        except Exception:
            errors += 1
            continue
        new_by_query.setdefault(query, 0)  # ran successfully → record its outcome

        for source in sources:
            try:
                candidate = _resolve_candidate(source, query)
            except Exception:
                errors += 1
                continue
            if candidate is None:  # generic routing URL, no company to stage
                continue
            found += 1
            if candidate.domain in existing_domains:
                continue
            existing_domains.add(candidate.domain)
            staged.append(candidate)
            new += 1
            new_by_query[query] += 1

    await _record_query_stats(session, user_id, new_by_query, deps.now())

    for candidate, description in zip(
        staged, await _resolve_descriptions(staged, deps), strict=True
    ):
        session.add(
            Approval(
                user_id=user_id,
                name=candidate.name,
                domain=candidate.domain,
                careers_url=candidate.careers_url,
                logo_url=favicon_url(candidate.domain),
                ats=candidate.ats,
                found_query=candidate.found_query,
                why=description,
                decision=None,
            )
        )

    await session.flush()
    return DiscoverResult(found=found, new=new, errors=errors)


async def _existing_domains(session: AsyncSession, user_id: UUID) -> set[str]:
    approval_domains = await session.scalars(
        select(Approval.domain).where(Approval.user_id == user_id, Approval.domain.is_not(None))
    )
    company_domains = await session.scalars(
        select(Company.domain).where(Company.user_id == user_id, Company.domain.is_not(None))
    )
    return {domain for domain in (*approval_domains, *company_domains) if domain is not None}


def _workable_view_company(host: str, path: str) -> str | None:
    """Workable serves a posting two ways: apply.workable.com/<company>/j/<id> (the first path
    segment IS the company) and jobs.workable.com/view/<id>/<title>-at-<company> (the first
    segment is the generic word "view"; the company is the '-at-' tail of the title slug).
    Recover the company from the second shape so the card names it, not "View"."""
    if host != "jobs.workable.com":
        return None
    segments = [s for s in path.split("/") if s]
    if len(segments) < 3 or segments[0] != "view":
        return None
    company = segments[-1].rpartition("-at-")[2].strip()
    return company or None


def _resolve_candidate(source: Source, query: str) -> _Candidate | None:
    """Turn a discovered URL into a staged-approval candidate, or None to skip it. When the URL
    sits on a known ATS host, the board token (path segment) is the only company-distinguishing
    part of the URL — the ATS host itself is shared across every company hosted there — so it's
    folded into `domain` to keep candidates from different companies from colliding. A generic
    routing segment (see `_GENERIC_PATH_SEGMENTS`) names no company and is dropped. The real
    company domain isn't known at this stage; that's the enrich stage's job."""
    parts = urlsplit(source.url)
    host = parts.netloc.lower().removeprefix("www.")
    if not host:
        raise ValueError(f"source URL has no host: {source.url!r}")

    ats = detect_ats(domain=None, careers_url=source.url, ats_hint=None)
    workable_company = _workable_view_company(host, parts.path)
    token = _path_token(parts.path)

    if workable_company is not None:
        domain = f"{workable_company}.workable.com"
        label = workable_company
    elif ats is not None and token and ats not in _SUBDOMAIN_TOKEN_ATS:
        if token in _GENERIC_PATH_SEGMENTS:
            return None
        domain = f"{token}.{host}"
        label = token
    else:
        domain = host
        label = host.split(".")[0]

    name = label.replace("-", " ").replace("_", " ").title()
    return _Candidate(domain=domain, ats=ats, careers_url=source.url, name=name, found_query=query)


def _path_token(path: str) -> str | None:
    segment = next((s for s in path.split("/") if s), None)
    return segment.lower() if segment else None


def _describe(candidate: _Candidate) -> str:
    """One line identifying a company for the description model: its name and domain, and
    nothing about the search that surfaced it — feeding the query made the model restate it
    ("X offers ML roles in Spain") instead of saying what the company actually does."""
    return f"{candidate.name} (domain {candidate.domain})"


async def _resolve_descriptions(candidates: list[_Candidate], deps: PipelineDeps) -> list[str]:
    """One factual sentence per staged approval describing what the company does (spec §7.2),
    batched into ONE call. The model returns a blank for any company it doesn't recognize —
    discovery is pre-crawl, so the only signal is the name/domain, and an honest "" (the card
    shows just the careers link) beats a guessed description a user would approve or reject on.
    Any failure — unreachable model, wrong count — blanks every description for the same reason.
    """
    if not candidates:
        return []
    try:
        descriptions = await deps.openai.approval_whys([_describe(c) for c in candidates])
    except Exception:
        descriptions = []
    if len(descriptions) != len(candidates):
        return ["" for _ in candidates]
    return [description.strip() for description in descriptions]
