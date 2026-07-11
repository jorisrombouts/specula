"""Discovery stage: seed-query the web for ATS-hosted job boards and stage them as approvals."""

from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Approval, Company, Lens, Targeting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.openai_client import Source
from specula_api.pipeline.source import ATS_ALLOWED_DOMAINS, detect_ats
from specula_api.pipeline.util import favicon_url


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
    """Effective ATS job-board search queries: '<role> jobs <region hint>'. Role titles are
    the outer loop so the first `cap` queries span multiple lenses (variety over the cap),
    deduped. Kept clean — the web_search tool is already domain-filtered to ATS hosts, so the
    query only needs the role + a location cue, not a pile of synonyms."""
    active = [lens for lens in lenses if lens.active]
    queries: list[str] = []
    seen: set[str] = set()
    for role_title in role_titles:
        for lens in active:
            hint = _region_hint(lens)
            query = " ".join(p for p in (role_title.strip(), "jobs", hint) if p)
            if not query or query in seen:
                continue
            seen.add(query)
            queries.append(query)
            if len(queries) >= cap:
                return queries
    return queries


async def discover(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> DiscoverResult:
    targeting = await session.get(Targeting, user_id)
    role_titles = targeting.role_titles if targeting is not None else []

    lenses = list((await session.scalars(select(Lens).where(Lens.user_id == user_id))).all())
    queries = build_seed_queries(role_titles, lenses, cap=deps.settings.discovery_max_searches)
    if not queries:
        return DiscoverResult()

    existing_domains = await _existing_domains(session, user_id)

    found = 0
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
            session.add(
                Approval(
                    user_id=user_id,
                    name=candidate.name,
                    domain=candidate.domain,
                    logo_url=favicon_url(candidate.domain),
                    ats=candidate.ats,
                    found_query=candidate.found_query,
                    why=_derive_why(candidate),
                    decision=None,
                )
            )
            new += 1

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

    if ats is not None and token:
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


def _derive_why(candidate: _Candidate) -> str:
    # TODO: LLM-generated why — replace this templated sentence once the enrich stage can ask
    # the model for a real rationale from the fetched company page.
    return f'Surfaced by the search "{candidate.found_query}" as "{candidate.name}".'
