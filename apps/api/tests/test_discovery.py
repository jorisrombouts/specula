from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Approval, Company, Lens, Targeting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.discovery import (
    DiscoverResult,
    _region_hint,
    _resolve_candidate,
    build_seed_queries,
    discover,
)
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import EnrichResult, ExtractionResult, Source

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"


class _StubOpenAI:
    """Hand-built OpenAIClient: returns fixed Sources per query, no network/fixtures.

    Keying a RecordedOpenAIClient fixture to `discover`'s exact per-query call (queries are
    assembled from role titles + lens seeds/scope, so the fixture filename would depend on
    that composition) is fiddlier than it's worth here — a stub keyed directly to the queries
    under test is clearer and just as faithful to the `OpenAIClient` Protocol.
    """

    def __init__(
        self, sources_by_query: dict[str, list[Source]], *, whys: list[str] | None = None
    ) -> None:
        self._sources_by_query = sources_by_query
        self._whys = whys
        self.calls: list[list[str]] = []
        self.why_calls: list[list[str]] = []

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        self.calls.append(list(queries))
        results: list[Source] = []
        for query in queries:
            results.extend(self._sources_by_query.get(query, []))
        return results

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
        self.why_calls.append(list(descriptions))
        if self._whys is None:
            raise NotImplementedError("no why stub configured")
        return self._whys

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        raise NotImplementedError

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        raise NotImplementedError

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


def _deps(openai: _StubOpenAI) -> PipelineDeps:
    return PipelineDeps(
        openai=openai,
        fetcher=RecordedFetcher(FIXTURES_DIR),
        settings=Settings(),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )


async def _seed_targeting_and_lens(session: AsyncSession, user_id: object) -> Lens:
    session.add(Targeting(user_id=user_id, role_titles=["ML Engineer"]))
    lens = Lens(
        user_id=user_id,
        name="Fintech",
        seeds=["fintech"],
        scope="Remote EU",
        modes=["Remote"],
        active=True,
    )
    session.add(lens)
    await session.flush()
    return lens


# --- discover -----------------------------------------------------------------


@requires_db
async def test_discover_writes_new_approvals_for_resolved_candidates(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    lens = await _seed_targeting_and_lens(db_session, user.id)

    queries = build_seed_queries(["ML Engineer"], [lens], cap=5)
    # the lens's own seed ("fintech") is now used, and comes first (verbatim)
    assert queries == ["fintech", "ML Engineer jobs Remote EU"]

    sources_by_query = {
        queries[0]: [
            Source(url="https://boards.greenhouse.io/acme/jobs/123", title="Acme role"),
            Source(url="https://jobs.lever.co/beta-corp/456", title="Beta role"),
        ]
    }
    deps = _deps(_StubOpenAI(sources_by_query))

    result = await discover(db_session, user.id, uuid4(), deps)

    assert result.found == 2
    assert result.new == 2
    assert result.errors == 0

    approvals = (
        await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
    ).all()
    by_domain = {a.domain: a for a in approvals}
    assert set(by_domain) == {"acme.boards.greenhouse.io", "beta-corp.jobs.lever.co"}

    acme = by_domain["acme.boards.greenhouse.io"]
    assert acme.ats == "greenhouse"
    assert acme.name == "Acme"
    assert acme.found_query == queries[0]
    assert acme.logo_url == "https://icons.duckduckgo.com/ip3/acme.boards.greenhouse.io.ico"
    assert acme.decision is None

    beta = by_domain["beta-corp.jobs.lever.co"]
    assert beta.ats == "lever"
    assert beta.name == "Beta Corp"
    assert beta.decision is None


@requires_db
async def test_discover_records_the_real_careers_url_on_the_approval(
    db_session: AsyncSession,
) -> None:
    """The discovered URL is the only true careers URL we ever get.

    Dropping it left enrich to guess `https://{domain}` — and for path-token ATSes that domain
    is fabricated by _resolve_candidate (acme.boards.greenhouse.io), which does not resolve, so
    enrich ran with no page text and the model guessed every field from the name alone.
    """
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    lens = await _seed_targeting_and_lens(db_session, user.id)
    queries = build_seed_queries(["ML Engineer"], [lens], cap=5)
    url = "https://boards.greenhouse.io/acme/jobs/123"
    deps = _deps(_StubOpenAI({queries[0]: [Source(url=url, title="Acme role")]}))

    await discover(db_session, user.id, uuid4(), deps)

    approval = await db_session.scalar(select(Approval).where(Approval.user_id == user.id))
    assert approval is not None
    assert approval.careers_url == url


@requires_db
async def test_discover_is_idempotent_on_rerun(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    lens = await _seed_targeting_and_lens(db_session, user.id)
    queries = build_seed_queries(["ML Engineer"], [lens], cap=5)
    sources_by_query = {
        queries[0]: [Source(url="https://boards.greenhouse.io/acme/jobs/123", title="Acme role")]
    }
    deps = _deps(_StubOpenAI(sources_by_query))

    first = await discover(db_session, user.id, uuid4(), deps)
    second = await discover(db_session, user.id, uuid4(), deps)

    assert first.new == 1
    assert second.found == 1
    assert second.new == 0

    approvals = (
        await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
    ).all()
    assert len(approvals) == 1


@requires_db
async def test_discover_skips_candidate_whose_domain_is_already_a_company(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    lens = await _seed_targeting_and_lens(db_session, user.id)
    queries = build_seed_queries(["ML Engineer"], [lens], cap=5)

    db_session.add(
        Company(user_id=user.id, name="Acme", domain="acme.boards.greenhouse.io", tracking=True)
    )
    await db_session.flush()

    sources_by_query = {
        queries[0]: [Source(url="https://boards.greenhouse.io/acme/jobs/123", title="Acme role")]
    }
    deps = _deps(_StubOpenAI(sources_by_query))

    result = await discover(db_session, user.id, uuid4(), deps)

    assert result.found == 1
    assert result.new == 0
    approvals = (
        await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
    ).all()
    assert approvals == []


@requires_db
async def test_discover_returns_zero_result_without_role_titles(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    deps = _deps(_StubOpenAI({}))

    result = await discover(db_session, user.id, uuid4(), deps)

    assert result == DiscoverResult()


# --- build_seed_queries ---------------------------------------------------------


def test_build_seed_queries_composes_role_and_region_hint() -> None:
    lens = Lens(user_id=uuid4(), name="Fintech", seeds=["fintech"], scope="Remote EU", active=True)
    assert build_seed_queries(["Staff Backend Engineer"], [lens], cap=5) == [
        "fintech",  # lens seed first (verbatim)
        "Staff Backend Engineer jobs Remote EU",
    ]


def test_build_seed_queries_uses_lens_seeds_first() -> None:
    """A lens's own discovery seeds are high-signal, user-crafted queries: they enter the
    query list verbatim and ahead of the generated '<role> jobs <hint>' combos."""
    lens = Lens(user_id=uuid4(), name="Fintech", seeds=["fintech"], scope="ES", active=True)
    assert build_seed_queries(["ML Engineer"], [lens], cap=5) == [
        "fintech",
        "ML Engineer jobs Spain",
    ]


def test_build_seed_queries_only_includes_active_lenses() -> None:
    active = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="ES", active=True)
    inactive = Lens(user_id=uuid4(), name="B", seeds=["climate"], scope="DE", active=False)
    queries = build_seed_queries(["ML Engineer"], [active, inactive], cap=10)
    # the inactive lens contributes neither its seed nor its scope
    assert queries == ["fintech", "ML Engineer jobs Spain"]


def test_build_seed_queries_dedups_identical_compositions() -> None:
    lens1 = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="ES", active=True)
    lens2 = Lens(user_id=uuid4(), name="B", seeds=["climate"], scope="ES", active=True)
    queries = build_seed_queries(["ML Engineer"], [lens1, lens2], cap=10)
    # both distinct seeds kept; the identical 'ML Engineer jobs Spain' composition appears once
    assert queries == ["fintech", "climate", "ML Engineer jobs Spain"]


def test_build_seed_queries_respects_cap() -> None:
    lens1 = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="ES", active=True)
    lens2 = Lens(user_id=uuid4(), name="B", seeds=["climate"], scope="DE", active=True)
    queries = build_seed_queries(["ML Engineer", "Data Scientist"], [lens1, lens2], cap=3)
    assert len(queries) == 3


def test_build_seed_queries_role_titles_are_the_outer_loop() -> None:
    """Every active lens is queried for the first role title before moving to the next role
    title — this is what gives the first `cap` queries variety across roles when the cap is
    hit mid-role, instead of exhausting one role across every lens first."""
    lens_de = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="DE", active=True)
    lens_es = Lens(user_id=uuid4(), name="B", seeds=["climate"], scope="ES", active=True)
    queries = build_seed_queries(["ML Engineer", "Data Scientist"], [lens_de, lens_es], cap=10)
    assert queries == [
        "fintech",  # lens seeds first, in lens order
        "climate",
        "ML Engineer jobs Germany",
        "ML Engineer jobs Spain",
        "Data Scientist jobs Germany",
        "Data Scientist jobs Spain",
    ]


# --- _region_hint ---------------------------------------------------------------


def test_region_hint_maps_known_country_codes() -> None:
    assert _region_hint(Lens(user_id=uuid4(), name="A", scope="ES", active=True)) == "Spain"
    assert _region_hint(Lens(user_id=uuid4(), name="A", scope="DE", active=True)) == "Germany"
    assert _region_hint(Lens(user_id=uuid4(), name="A", scope="NL", active=True)) == "Netherlands"


def test_region_hint_uses_first_segment_of_a_city_country_scope() -> None:
    lens = Lens(user_id=uuid4(), name="A", scope="Berlin, DE", active=True)
    assert _region_hint(lens) == "Berlin"


def test_region_hint_any_region_scope_falls_back_to_remote_or_eu_name_cue() -> None:
    remote_lens = Lens(user_id=uuid4(), name="Remote EU roles", scope="Any region", active=True)
    eu_lens = Lens(user_id=uuid4(), name="EU-wide", scope="Any region", active=True)
    assert _region_hint(remote_lens) == "remote EU"
    assert _region_hint(eu_lens) == "remote EU"


def test_region_hint_any_region_scope_without_remote_or_eu_name_is_empty() -> None:
    lens = Lens(user_id=uuid4(), name="All", scope="Any region", active=True)
    assert _region_hint(lens) == ""


def test_region_hint_blank_scope_and_generic_name_is_empty() -> None:
    lens = Lens(user_id=uuid4(), name="Foreign HQ", scope="", active=True)
    assert _region_hint(lens) == ""


def test_region_hint_scope_takes_precedence_over_name_cue() -> None:
    """A real scope wins even when the lens name happens to mention 'remote'/'eu'."""
    lens = Lens(user_id=uuid4(), name="Remote EU", scope="ES", active=True)
    assert _region_hint(lens) == "Spain"


# --- _resolve_candidate ----------------------------------------------------------


def test_resolve_candidate_folds_path_token_for_smartrecruiters() -> None:
    """SmartRecruiters (like Greenhouse/Lever/Ashby) hosts every company's board at a
    shared host with a path-based token, so the token must fold into the domain to keep
    different companies from colliding."""
    source = Source(url="https://jobs.smartrecruiters.com/DeliveryHero/744-title", title="x")
    candidate = _resolve_candidate(source, "query")
    assert candidate.domain == "deliveryhero.jobs.smartrecruiters.com"
    assert candidate.ats == "smartrecruiters"
    assert candidate.name == "Deliveryhero"


def test_resolve_candidate_folds_path_token_for_workable() -> None:
    source = Source(url="https://apply.workable.com/mondu/j/CAAC2E000A", title="x")
    candidate = _resolve_candidate(source, "query")
    assert candidate.domain == "mondu.apply.workable.com"
    assert candidate.ats == "workable"


def test_resolve_candidate_does_not_fold_subdomain_token_for_recruitee() -> None:
    """Recruitee hosts each company at its own subdomain (bunq.recruitee.com) — the host is
    already company-distinguishing, so folding the job page's path segment ("o") into the
    domain would be wrong, unlike the shared-host ATSes above."""
    source = Source(url="https://bunq.recruitee.com/o/operational-risk-intern-1", title="x")
    candidate = _resolve_candidate(source, "query")
    assert candidate.domain == "bunq.recruitee.com"
    assert candidate.ats == "recruitee"
    assert candidate.name == "Bunq"


def test_resolve_candidate_does_not_fold_subdomain_token_for_personio() -> None:
    source = Source(url="https://smava.jobs.personio.de/job/275557", title="x")
    candidate = _resolve_candidate(source, "query")
    assert candidate.domain == "smava.jobs.personio.de"
    assert candidate.ats == "personio"
    assert candidate.name == "Smava"


# --- LLM-written why (spec §7.2) --------------------------------------------------


async def _discover_two(db_session: AsyncSession, openai: _StubOpenAI) -> list[Approval]:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    lens = await _seed_targeting_and_lens(db_session, user.id)
    queries = build_seed_queries(["ML Engineer"], [lens], cap=5)
    openai._sources_by_query = {
        queries[0]: [
            Source(url="https://boards.greenhouse.io/acme/jobs/1", title="Acme role"),
            Source(url="https://jobs.lever.co/beta-corp/2", title="Beta role"),
        ]
    }
    await discover(db_session, user.id, uuid4(), _deps(openai))
    return list(
        await db_session.scalars(
            select(Approval).where(Approval.user_id == user.id).order_by(Approval.name)
        )
    )


@requires_db
async def test_why_is_written_by_the_model(db_session: AsyncSession) -> None:
    openai = _StubOpenAI({}, whys=["Acme ships ML infra.", "Beta is hiring in the EU."])

    approvals = await _discover_two(db_session, openai)

    assert [a.why for a in approvals] == ["Acme ships ML infra.", "Beta is hiring in the EU."]
    # ONE batched call covering both candidates, not one call each.
    assert len(openai.why_calls) == 1
    assert len(openai.why_calls[0]) == 2


@requires_db
async def test_description_is_blank_when_the_model_fails(
    db_session: AsyncSession,
) -> None:
    """A dead description call degrades to a blank, not a guess: the card then shows just the
    company name and careers link, never a fabricated 'what they do'."""
    approvals = await _discover_two(db_session, _StubOpenAI({}, whys=None))

    assert all(a.why == "" for a in approvals)


@requires_db
async def test_description_is_blank_when_the_model_returns_the_wrong_count(
    db_session: AsyncSession,
) -> None:
    """A short list would silently mis-attribute one company's description to another, so a
    count mismatch blanks every description rather than zipping them out of order."""
    approvals = await _discover_two(db_session, _StubOpenAI({}, whys=["only one sentence"]))

    assert all(a.why == "" for a in approvals)
