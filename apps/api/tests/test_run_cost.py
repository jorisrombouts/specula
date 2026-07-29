"""OBS lane: usage capture, run-timing and tenant isolation for the ledger that
services/run.py writes. Fixtures are the committed recorded pipeline fixtures; OpenAI results
are hand-built stubs (see test_pipeline_integration for why) wrapped in the real metering client
so token accounting is exercised end to end — no live spend."""

import json
import logging
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Approval, CandidateProfile, Company, Lens, LlmCost, Targeting
from specula_api.observability import ContextFilter, JsonFormatter, configure_logging
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.discovery import build_seed_queries
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import (
    EnrichResult,
    ExtractionResult,
    MeteringOpenAIClient,
    RecordedOpenAIClient,
    Source,
    UsageRecord,
    UsageSink,
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


def _metered_deps(inner: _IngestOpenAI, sink: UsageSink) -> PipelineDeps:
    settings = Settings()
    return PipelineDeps(
        openai=MeteringOpenAIClient(inner, sink, settings),
        fetcher=RecordedFetcher(FIXTURES_DIR),
        settings=settings,
        now=lambda: FROZEN_NOW,
        usage_sink=sink,
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
    # No discovery seeds here: these are usage tests, and an empty-seed lens emits exactly one
    # composed query, keeping the discovery run to a single measurable web search.
    lens = Lens(user_id=user_id, name="Remote EU", seeds=[], scope="Remote EU", active=True)
    session.add(lens)
    await session.flush()
    [query] = build_seed_queries(["Backend Engineer"], [lens], cap=5)
    return query.text


async def _rows(session: AsyncSession, user_id: UUID) -> list[LlmCost]:
    return list(await session.scalars(select(LlmCost).where(LlmCost.user_id == user_id)))


@requires_db
async def test_ingest_writes_llm_cost_rows_with_stage_model_and_tokens(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    query = await _seed(db_session, user.id)

    setup = _metered_deps(
        _IngestOpenAI({query: [Source(url=_DISCOVERED_JOB_URL, title="Senior Backend Engineer")]}),
        UsageSink(),
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

    ingest_sink = UsageSink()
    ingest_deps = _metered_deps(_IngestOpenAI({}), ingest_sink)
    await ingest_company(db_session, user.id, company_id, ingest_deps)

    ingest_rows = [
        r
        for r in await _rows(db_session, user.id)
        if r.run_id is None and r.company_id == company_id
    ]
    assert ingest_rows, "ingest wrote no usage rows"

    settings = Settings()
    by_stage = {r.stage for r in ingest_rows}
    assert {"extract", "embed", "rationale"} <= by_stage
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
        _metered_deps(_IngestOpenAI({}), UsageSink()),
    )

    assert [r for r in await _rows(db_session, user.id) if r.company_id == company.id] == []
    assert company.logo_url is None


@requires_db
async def test_discovery_run_records_usage_rows_and_duration(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    query = await _seed(db_session, user.id)

    sink = UsageSink()
    deps = _metered_deps(_IngestOpenAI({query: [Source(url=_DISCOVERED_JOB_URL, title="x")]}), sink)
    run = await create_run(db_session, user.id)
    await run_discovery(db_session, user.id, run.id, deps)

    assert run.status == "done"
    assert run.duration_ms is not None
    discovery_rows = [
        r for r in await _rows(db_session, user.id) if r.run_id == run.id and r.stage == "discovery"
    ]
    assert discovery_rows


@requires_db
async def test_crashed_run_is_marked_error_and_does_not_escape(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crashed run must not propagate out of `run_discovery`.

    `trigger_discovery_run` wraps this in `tenant_session`, which rolls back and re-raises on
    any escaping exception — so re-raising here discards BOTH the status="error" write and the
    usage rows, leaving the run stuck at "queued" forever. The UI reads queued as in-progress
    (`busy = status === "queued" || "running"`), so the button spins indefinitely.

    The failure is injected at `discover` itself: discovery.py guards each query with its own
    broad `except Exception`, so a raising OpenAI stub is absorbed into `result.errors` and the
    run still finishes "done". Only an unhandled failure reaches the handler under test.
    """
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    await _seed(db_session, user.id)

    async def _explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("discovery exploded")

    monkeypatch.setattr("specula_api.services.run.discover", _explode)

    sink = UsageSink()
    sink.add(
        UsageRecord(
            stage="discovery",
            model="gpt-4o",
            prompt_tokens=120,
            completion_tokens=30,
            embed_tokens=0,
        )
    )
    deps = _metered_deps(_IngestOpenAI({}), sink)
    run = await create_run(db_session, user.id)

    await run_discovery(db_session, user.id, run.id, deps)  # must not raise

    assert run.status == "error"
    assert run.finished_at is not None
    # Tokens already spent before the crash are still owed to the ledger.
    crashed_rows = [r for r in await _rows(db_session, user.id) if r.run_id == run.id]
    assert [r.prompt_tokens for r in crashed_rows] == [120]


@requires_db
async def test_llm_costs_are_tenant_isolated(db_session: AsyncSession) -> None:
    a = await make_user(db_session)
    b = await make_user(db_session)

    await set_tenant(db_session, a.id)
    db_session.add(LlmCost(user_id=a.id, stage="score", model="gpt-4o-mini"))
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
        UsageSink(),
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
