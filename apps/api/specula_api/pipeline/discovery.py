"""Discovery stage: seed-query the web for ATS-hosted job boards and stage them as approvals."""

from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Approval, Company, Lens, Targeting
from specula_api.observability import get_logger
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.openai_client import Source
from specula_api.pipeline.source import ATS_ALLOWED_DOMAINS, detect_ats
from specula_api.pipeline.util import favicon_url

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


def build_seed_queries(role_titles: list[str], lenses: list[Lens], *, cap: int) -> list[str]:
    """Effective ATS job-board search queries. Each active lens's own discovery seeds are
    high-signal, user-crafted queries and go FIRST (verbatim); then the generated
    '<role> jobs <region hint>' combos (role titles outer, so the cap spans lenses).
    Deduped, capped at `cap`. The web_search tool is already domain-filtered to ATS hosts,
    so a query only needs the role/seed + a location cue, not a pile of synonyms."""
    active = [lens for lens in lenses if lens.active]
    queries: list[str] = []
    seen: set[str] = set()

    def _add(query: str) -> bool:
        """Append a deduped, non-empty query; return True once the cap is full."""
        query = query.strip()
        if query and query not in seen:
            seen.add(query)
            queries.append(query)
        return len(queries) >= cap

    for lens in active:
        for seed in lens.seeds:
            if _add(seed):
                return queries
    for role_title in role_titles:
        for lens in active:
            if _add(" ".join(p for p in (role_title.strip(), "jobs", _region_hint(lens)) if p)):
                return queries
    return queries


async def discover(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> DiscoverResult:
    targeting = await session.get(Targeting, user_id)
    role_titles = targeting.role_titles if targeting is not None else []

    lenses = list((await session.scalars(select(Lens).where(Lens.user_id == user_id))).all())
    queries = build_seed_queries(role_titles, lenses, cap=deps.settings.discovery_max_searches)
    _log.info("pipeline.stage", extra={"stage": "discovery", "queries": len(queries)})
    if not queries:
        return DiscoverResult()

    existing_domains = await _existing_domains(session, user_id)

    found = 0
    staged: list[_Candidate] = []
    new = 0
    errors = 0
    for query in queries:
        try:
            sources = await deps.openai.discover_sources(
                [query], allowed_domains=ATS_ALLOWED_DOMAINS
            )
        except Exception:
            errors += 1
            continue

        for source in sources:
            try:
                candidate = _resolve_candidate(source, query)
            except Exception:
                errors += 1
                continue
            found += 1
            if candidate.domain in existing_domains:
                continue
            existing_domains.add(candidate.domain)
            staged.append(candidate)
            new += 1

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


def _resolve_candidate(source: Source, query: str) -> _Candidate:
    """Turn a discovered URL into a staged-approval candidate. When the URL sits on a known
    ATS host, the board token (path segment) is the only company-distinguishing part of the
    URL — the ATS host itself is shared across every company hosted there — so it's folded
    into `domain` to keep candidates from different companies from colliding. The real company
    domain isn't known at this stage; that's the enrich stage's job."""
    parts = urlsplit(source.url)
    host = parts.netloc.lower().removeprefix("www.")
    if not host:
        raise ValueError(f"source URL has no host: {source.url!r}")

    ats = detect_ats(domain=None, careers_url=source.url, ats_hint=None)
    token = _path_token(parts.path)

    if ats is not None and token and ats not in _SUBDOMAIN_TOKEN_ATS:
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
