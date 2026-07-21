"""End-to-end pipeline integration test: discovery -> approval -> ingest (enrich/fetch/
extract/embed/score) -> render-ready read model, all against `build_recorded_deps` fixtures
(deterministic, no network/API key) with a frozen clock.

`discover_sources` is a hand-built stub rather than a `RecordedOpenAIClient` fixture keyed to
the composed discovery query — see `tests/test_discovery.py`'s docstring for why that keying
is fragile. `enrich_company`/`extract_posting` are likewise hand-built stubs (matching
`tests/test_score.py`'s `_FullStubOpenAI` pattern): a company/posting's exact page text isn't
the point of this test, and stubbing keeps it decoupled from HTML fixture content. `embed`
delegates to `RecordedOpenAIClient`'s deterministic pseudo-vector fallback, and `rationale`
echoes its computed inputs (matching `test_score.py`'s `_EchoingOpenAI`) since a fixture can't
be pre-recorded for arbitrary computed factor values. The fetch stage runs through the REAL
`RecordedFetcher` against committed HTTP fixtures (including two added alongside this test:
the greenhouse board-listing API response and one fetchable job page), so the crawl -> content
hash -> provenance-shell half of the pipeline is exercised for real.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import (
    Approval,
    CandidateProfile,
    Company,
    Lens,
    Posting,
    Score,
    Targeting,
)
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.discovery import build_seed_queries
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import (
    EnrichResult,
    ExtractionResult,
    RecordedOpenAIClient,
    Source,
)
from specula_api.services.approval import apply_decision
from specula_api.services.insights import compute_insights
from specula_api.services.jobs import get_job, list_jobs
from specula_api.services.run import create_run, ingest_company, run_discovery

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"
FROZEN_NOW = datetime(2026, 7, 5, tzinfo=UTC)

_DISCOVERED_JOB_URL = "https://boards.greenhouse.io/acme/jobs/4123456"

_ENRICH_RESULT = EnrichResult(
    hq_country="DE",
    hq_confidence=90,
    comp_estimate="€80k-€110k, DE market",
    careers_url="https://acme.example/careers",
    ats="greenhouse",
)

_EXTRACT_RESULT = ExtractionResult(
    title="Senior Backend Engineer",
    role_family="Backend Engineering",
    city="Berlin",
    country="DE",
    hq_country="DE",
    work_mode="Hybrid",
    seniority="Senior",
    required_skills=["Python", "PostgreSQL"],
    nice_to_have=["Kubernetes"],
    contract="Permanent",
    summary="Senior backend role at Acme, hybrid in Berlin.",
    extraction_confidence=85,
)


class _IntegrationOpenAI:
    """Hybrid recorded/stub `OpenAIClient` — see the module docstring for the rationale
    behind each method."""

    def __init__(self, sources_by_query: dict[str, list[Source]]) -> None:
        self._sources_by_query = sources_by_query
        self._recorded = RecordedOpenAIClient(FIXTURES_DIR)

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        results: list[Source] = []
        for query in queries:
            results.extend(self._sources_by_query.get(query, []))
        return results

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        return _ENRICH_RESULT

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        return _EXTRACT_RESULT

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._recorded.embed(texts)

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        return (
            f"role={factors['role']} skill={factors['skill']} "
            f"overlap={overlap[0]}/{overlap[1]} red_flag={red_flag or 'none'}"
        )

    async def aclose(self) -> None:
        return None


def _deps(openai: _IntegrationOpenAI) -> PipelineDeps:
    return PipelineDeps(
        openai=openai,
        fetcher=RecordedFetcher(FIXTURES_DIR),
        settings=Settings(),
        now=lambda: FROZEN_NOW,
    )


async def _seed_targeting_and_pool(session: AsyncSession, user_id: UUID) -> tuple[Lens, str]:
    """Targeting + CandidateProfile + one active Lens. Returns the lens and the exact
    composed discovery query so the discover stub can be keyed to it precisely."""
    session.add(
        Targeting(
            user_id=user_id,
            # Must match the ATS fixture's posting title — fetch.py's title_matches_roles()
            # relevance gate drops feed entries that don't contain a target role title.
            role_titles=["Backend Engineer"],
            seniority=["Senior"],
            must_haves=["Python"],
        )
    )
    session.add(CandidateProfile(user_id=user_id, skills=["Python", "PostgreSQL"]))
    lens = Lens(
        user_id=user_id,
        name="Remote EU",
        seeds=["backend"],
        scope="Remote EU",
        modes=["Remote", "Hybrid"],
        active=True,
    )
    session.add(lens)
    await session.flush()
    [query] = build_seed_queries(["Backend Engineer"], [lens], cap=5)
    return lens, query


@requires_db
async def test_full_pipeline_discovery_to_render_ready_job(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    _lens, query = await _seed_targeting_and_pool(db_session, user.id)

    deps = _deps(
        _IntegrationOpenAI(
            {query: [Source(url=_DISCOVERED_JOB_URL, title="Senior Backend Engineer - Acme")]}
        )
    )

    # --- 1. discovery -----------------------------------------------------------
    run = await create_run(db_session, user.id)
    await run_discovery(db_session, user.id, run.id, deps)

    assert run.status == "done"
    found, new = run.stats["found"], run.stats["new"]
    assert isinstance(found, int)
    assert isinstance(new, int)
    assert found >= 1
    assert new >= 1

    approvals = (
        await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
    ).all()
    assert len(approvals) >= 1
    assert all(a.decision is None for a in approvals)

    # --- 2. approve one company, then ingest it directly -------------------------
    approval = approvals[0]
    result = await apply_decision(db_session, user.id, approval.id, "approve")
    assert result is not None
    _decided, company_id = result
    assert company_id is not None

    await ingest_company(db_session, user.id, company_id, deps)

    company = await db_session.get(Company, company_id)
    assert company is not None
    assert company.hq_country == _ENRICH_RESULT.hq_country
    assert company.hq_confidence == _ENRICH_RESULT.hq_confidence
    assert company.comp_estimate == _ENRICH_RESULT.comp_estimate

    postings = (
        await db_session.scalars(
            select(Posting).where(Posting.user_id == user.id, Posting.company_id == company_id)
        )
    ).all()
    assert len(postings) >= 1
    real_postings = [p for p in postings if p.source_url == _DISCOVERED_JOB_URL]
    assert len(real_postings) == 1
    extracted = real_postings[0]
    assert extracted.title == "Senior Backend Engineer"
    assert extracted.required_skills == ["Python", "PostgreSQL"]
    assert extracted.extraction_confidence == 85

    score = await db_session.get(Score, extracted.id)
    assert score is not None
    assert score.rationale != ""

    # --- 3. render-ready read model ------------------------------------------------
    job = await get_job(db_session, user.id, extracted.id)
    assert job is not None
    assert job.match > 0
    assert job.rationale != ""

    jobs_response = await list_jobs(db_session, user.id, None, "match")
    assert extracted.id in {UUID(j.id) for j in jobs_response.jobs}

    # --- 4. a low-confidence posting is excluded from Insights ---------------------
    low_conf = Posting(
        user_id=user.id,
        company_id=company_id,
        source="scrape",
        source_url="https://acme.example/jobs/low-confidence",
        content_hash="low-conf-hash",
        title="Mystery Role",
        required_skills=["Cobol"],  # unique skill — proves exclusion from skill_demand
        posted_at=date.today(),
        extraction_confidence=30,  # below LOW_CONFIDENCE_THRESHOLD (50)
    )
    db_session.add(low_conf)
    await db_session.flush()

    insights = await compute_insights(db_session, user.id, "8w")
    assert insights.low_conf_excluded >= 1
    assert "cobol" not in {sd.skill.casefold() for sd in insights.skill_demand}


@requires_db
async def test_run_discovery_seeds_no_approvals_without_targeting(
    db_session: AsyncSession,
) -> None:
    """Sanity check: without Targeting/role_titles, discovery finds nothing (used to make
    sure the frozen-clock helper `_deps` above is exercised independently of the seeded-pool
    path — a run with an empty pool still transitions cleanly to "done")."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    run = await create_run(db_session, user.id)

    await run_discovery(db_session, user.id, run.id, _deps(_IntegrationOpenAI({})))

    assert run.status == "done"
    assert run.stats == {"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 0}
