"""OBS lane: cost capture, run-timing and tenant isolation for the ledger that
services/run.py writes. Fixtures are the committed recorded pipeline fixtures; OpenAI results
are hand-built stubs (see test_pipeline_integration for why) wrapped in the real metering client
so token/cost math is exercised end to end — no live spend."""

import json
import logging
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import OPENAI_PRICING, Settings
from specula_api.db.models import Approval, CandidateProfile, Company, Lens, LlmCost, Targeting
from specula_api.observability import ContextFilter, JsonFormatter, configure_logging
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.discovery import build_seed_queries
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import (
    CostSink,
    EnrichResult,
    ExtractionResult,
    MeteringOpenAIClient,
    RecordedOpenAIClient,
    Source,
)
from specula_api.services.approval import apply_decision
from specula_api.services.run import create_run, ingest_company, run_discovery

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"
FROZEN_NOW = datetime(2026, 7, 5, tzinfo=UTC)
_DISCOVERED_JOB_URL = "https://boards.greenhouse.io/acme/jobs/4123456"

_ENRICH = EnrichResult(hq_country="DE", hq_confidence=90, ats="greenhouse")
_EXTRACT = ExtractionResult(
    title="Senior Backend Engineer",
    role_family="Backend Engineering",
    seniority="Senior",
    required_skills=["Python", "PostgreSQL"],
    summary="Senior backend role at Acme.",
    extraction_confidence=85,
)


class _IngestOpenAI:
    """Discovery keyed by query; enrich/extract fixed; embed via recorded pseudo-vectors;
    rationale echoes."""

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
        return _ENRICH

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        return _EXTRACT

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._recorded.embed(texts)

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
        return ["worth a look" for _ in descriptions]

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        return f"role={factors['role']} skill={factors['skill']}"

    async def aclose(self) -> None:
        return None


def _metered_deps(inner: _IngestOpenAI, sink: CostSink) -> PipelineDeps:
    settings = Settings()
    return PipelineDeps(
        openai=MeteringOpenAIClient(inner, sink, settings),
        fetcher=RecordedFetcher(FIXTURES_DIR),
        settings=settings,
        now=lambda: FROZEN_NOW,
        cost_sink=sink,
    )


async def _seed(session: AsyncSession, user_id: UUID) -> str:
    session.add(
        Targeting(
            user_id=user_id,
            role_titles=["Backend Engineer"],
            seniority=["Senior"],
            must_haves=["Python"],
        )
    )
    session.add(CandidateProfile(user_id=user_id, skills=["Python", "PostgreSQL"]))
    # No discovery seeds here: these are cost tests, and an empty-seed lens emits exactly one
    # composed query, keeping the discovery run to a single measurable web search.
    lens = Lens(user_id=user_id, name="Remote EU", seeds=[], scope="Remote EU", active=True)
    session.add(lens)
    await session.flush()
    [query] = build_seed_queries(["Backend Engineer"], [lens], cap=5)
    return query.text


def _expected_cost(row: LlmCost) -> Decimal:
    price = OPENAI_PRICING[row.model]
    usd = (
        row.prompt_tokens * price["prompt"]
        + row.completion_tokens * price["completion"]
        + row.embed_tokens * price["embed"]
    ) / 1_000_000
    return Decimal(str(usd)).quantize(Decimal("0.000001"))


async def _rows(session: AsyncSession, user_id: UUID) -> list[LlmCost]:
    return list(await session.scalars(select(LlmCost).where(LlmCost.user_id == user_id)))


@requires_db
async def test_ingest_writes_llm_cost_rows_with_stage_model_and_pricing_cost(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    query = await _seed(db_session, user.id)

    setup = _metered_deps(
        _IngestOpenAI({query: [Source(url=_DISCOVERED_JOB_URL, title="Senior Backend Engineer")]}),
        CostSink(),
    )
    run = await create_run(db_session, user.id)
    await run_discovery(db_session, user.id, run.id, setup)

    approval = (
        await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
    ).first()
    assert approval is not None
    decided = await apply_decision(db_session, user.id, approval.id, "approve")
    assert decided is not None
    _, company_id = decided
    assert company_id is not None

    ingest_sink = CostSink()
    ingest_deps = _metered_deps(_IngestOpenAI({}), ingest_sink)
    await ingest_company(db_session, user.id, company_id, ingest_deps)

    ingest_rows = [
        r
        for r in await _rows(db_session, user.id)
        if r.run_id is None and r.company_id == company_id
    ]
    assert ingest_rows, "ingest wrote no cost rows"

    settings = Settings()
    by_stage = {r.stage for r in ingest_rows}
    assert {"extract", "embed", "rationale"} <= by_stage
    for row in ingest_rows:
        assert row.cost_usd == _expected_cost(row)
    extract_rows = [r for r in ingest_rows if r.stage == "extract"]
    assert all(r.model == settings.openai_extract_model for r in extract_rows)
    embed_rows = [r for r in ingest_rows if r.stage == "embed"]
    assert all(r.model == settings.openai_embed_model for r in embed_rows)
    assert all(r.embed_tokens > 0 and r.prompt_tokens == 0 for r in embed_rows)


@requires_db
async def test_ingest_skips_opted_out_company(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com", opt_out=True)
    db_session.add(company)
    await db_session.flush()

    await ingest_company(
        db_session,
        user.id,
        company.id,
        _metered_deps(_IngestOpenAI({}), CostSink()),
    )

    assert [r for r in await _rows(db_session, user.id) if r.company_id == company.id] == []
    assert company.logo_url is None


@requires_db
async def test_discovery_run_records_cost_rollup_and_duration(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    query = await _seed(db_session, user.id)

    sink = CostSink()
    deps = _metered_deps(_IngestOpenAI({query: [Source(url=_DISCOVERED_JOB_URL, title="x")]}), sink)
    run = await create_run(db_session, user.id)
    await run_discovery(db_session, user.id, run.id, deps)

    assert run.status == "done"
    assert run.duration_ms is not None
    assert run.cost_usd is not None
    discovery_rows = [
        r for r in await _rows(db_session, user.id) if r.run_id == run.id and r.stage == "discovery"
    ]
    assert discovery_rows
    assert run.cost_usd == sum((r.cost_usd for r in discovery_rows), Decimal("0"))


@requires_db
async def test_llm_costs_are_tenant_isolated(db_session: AsyncSession) -> None:
    a = await make_user(db_session)
    b = await make_user(db_session)

    await set_tenant(db_session, a.id)
    db_session.add(
        LlmCost(user_id=a.id, stage="score", model="gpt-4o-mini", cost_usd=Decimal("0.01"))
    )
    await db_session.flush()
    assert [r.id for r in await _rows(db_session, a.id)]  # A sees its own row

    await set_tenant(db_session, b.id)
    assert await _rows(db_session, b.id) == []  # B sees none of A's ledger


class _StageCapture(logging.Handler):
    """Collects the `stage` of every `pipeline.stage` structured line the pipeline emits."""

    def __init__(self) -> None:
        super().__init__()
        self.addFilter(ContextFilter())
        self.setFormatter(JsonFormatter())
        self.stages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        obj = json.loads(self.format(record))
        if obj["message"] == "pipeline.stage":
            self.stages.append(obj["stage"])


@pytest.fixture
def stage_capture() -> Iterator[_StageCapture]:
    # Mirror app startup: create_app configures logging (and re-enables the specula subtree
    # after Alembic's fileConfig disabled it) before the background pipeline ever runs.
    configure_logging(Settings())
    handler = _StageCapture()
    logger = logging.getLogger("specula")
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


@requires_db
async def test_pipeline_stages_emit_stage_logs(
    db_session: AsyncSession, stage_capture: _StageCapture
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    query = await _seed(db_session, user.id)

    deps = _metered_deps(
        _IngestOpenAI({query: [Source(url=_DISCOVERED_JOB_URL, title="Senior Backend Engineer")]}),
        CostSink(),
    )
    run = await create_run(db_session, user.id)
    await run_discovery(db_session, user.id, run.id, deps)

    approval = (
        await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
    ).first()
    assert approval is not None
    decided = await apply_decision(db_session, user.id, approval.id, "approve")
    assert decided is not None
    _, company_id = decided
    assert company_id is not None
    await ingest_company(db_session, user.id, company_id, deps)

    emitted = set(stage_capture.stages)
    assert {"discovery", "enrich", "source", "extract", "embed", "dedup", "score"} <= emitted
