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
from specula_api.pipeline.discovery import DiscoverResult, build_seed_queries, discover
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

    def __init__(self, sources_by_query: dict[str, list[Source]]) -> None:
        self._sources_by_query = sources_by_query
        self.calls: list[list[str]] = []

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        self.calls.append(list(queries))
        results: list[Source] = []
        for query in queries:
            results.extend(self._sources_by_query.get(query, []))
        return results

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
    assert queries == ["ML Engineer fintech Remote EU"]

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


def test_build_seed_queries_combines_role_title_seeds_and_scope() -> None:
    lens = Lens(user_id=uuid4(), name="Fintech", seeds=["fintech"], scope="Remote EU", active=True)
    assert build_seed_queries(["Staff Backend Engineer"], [lens], cap=5) == [
        "Staff Backend Engineer fintech Remote EU"
    ]


def test_build_seed_queries_only_includes_active_lenses() -> None:
    active = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="", active=True)
    inactive = Lens(user_id=uuid4(), name="B", seeds=["climate"], scope="", active=False)
    queries = build_seed_queries(["ML Engineer"], [active, inactive], cap=10)
    assert queries == ["ML Engineer fintech"]


def test_build_seed_queries_dedups_identical_compositions() -> None:
    lens1 = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="", active=True)
    lens2 = Lens(user_id=uuid4(), name="B", seeds=["fintech"], scope="", active=True)
    queries = build_seed_queries(["ML Engineer"], [lens1, lens2], cap=10)
    assert queries == ["ML Engineer fintech"]


def test_build_seed_queries_respects_cap() -> None:
    lens1 = Lens(user_id=uuid4(), name="A", seeds=["fintech"], scope="", active=True)
    lens2 = Lens(user_id=uuid4(), name="B", seeds=["climate"], scope="", active=True)
    queries = build_seed_queries(["ML Engineer", "Data Scientist"], [lens1, lens2], cap=3)
    assert len(queries) == 3
