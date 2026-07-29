from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import settings
from specula_api.db.models import CandidateProfile, Company, LlmCost, Posting, Run, Targeting
from specula_api.db.session import tenant_session
from specula_api.observability import get_logger, log_context
from specula_api.pipeline.dedup import dedup_company
from specula_api.pipeline.deps import PipelineDeps, build_deps
from specula_api.pipeline.discovery import discover
from specula_api.pipeline.embeddings import embed_posting
from specula_api.pipeline.enrich import enrich_company
from specula_api.pipeline.extract import extract_posting
from specula_api.pipeline.fetch import fetch_postings
from specula_api.pipeline.openai_client import EnrichResult
from specula_api.pipeline.score import ensure_candidate_vectors, score_posting
from specula_api.pipeline.util import favicon_url

_log = get_logger("pipeline.run")


async def _persist_usage(
    session: AsyncSession,
    user_id: UUID,
    deps: PipelineDeps,
    *,
    run_id: UUID | None,
    company_id: UUID | None,
) -> None:
    """Drain the usage sink into `llm_costs` rows (one per metered call). Company ingest
    creates no Run, so its rows carry `run_id=None, company_id=<id>` (OBS→DASH contract).
    Draining makes this safe to call once per run/ingest without double-counting. Attributes
    the ENTIRE sink to the single `(run_id, company_id)` pair it's called with — correct today
    because nothing meters between per-company ingests in `refresh_all_jobs`, but a top-level
    metered call added to that loop (mirroring `rescore_all`) would silently bill its tokens
    to the first company ingested."""
    sink = deps.usage_sink
    if sink is None:
        return
    created_at = deps.now()
    for record in sink.records:
        session.add(
            LlmCost(
                user_id=user_id,
                run_id=run_id,
                company_id=company_id,
                stage=record.stage,
                model=record.model,
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                embed_tokens=record.embed_tokens,
                created_at=created_at,
            )
        )
    sink.records.clear()
    await session.flush()


async def create_run(session: AsyncSession, user_id: UUID, kind: str = "on_demand") -> Run:
    run = Run(user_id=user_id, kind=kind)
    session.add(run)
    await session.flush()
    return run


async def get_run(session: AsyncSession, user_id: UUID, run_id: UUID) -> Run | None:
    run = await session.get(Run, run_id)
    if run is None or run.user_id != user_id:
        return None
    return run


async def latest_run(session: AsyncSession, user_id: UUID) -> Run | None:
    # Feeds the Approvals-page "checked Nd ago" indicator, which is about DISCOVERY (when we last
    # looked for new companies). Rescore and refresh runs are job-side, not discovery, so they
    # must not supersede that line — they still live in the DB + cost dashboard.
    run: Run | None = await session.scalar(
        select(Run)
        .where(Run.user_id == user_id, Run.kind.notin_(["rescore", "refresh"]))
        .order_by(Run.created_at.desc())
        .limit(1)
    )
    return run


async def finalize_run(
    session: AsyncSession, run: Run, stats: dict[str, object], *, status: str
) -> None:
    run.status = status
    run.finished_at = datetime.now(UTC)
    if run.started_at is not None:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    run.stats = stats
    await session.flush()


_ERROR_STATS: dict[str, object] = {
    "found": 0,
    "new": 0,
    "closed": 0,
    "low_conf_excluded": 0,
    "errors": 1,
}


async def run_discovery(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> None:
    run = await get_run(session, user_id, run_id)
    if run is None:
        return

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()

    with log_context(user_id=user_id, run_id=run_id):
        _log.info("run.discovery.start", extra={"stage": "discovery"})
        try:
            result = await discover(session, user_id, run_id, deps)
            stats: dict[str, object] = {
                "found": result.found,
                "new": result.new,
                "closed": 0,
                "low_conf_excluded": 0,
                "errors": result.errors,
            }
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
            await finalize_run(session, run, stats, status="done")
            _log.info("run.discovery.done", extra={"stage": "discovery"})
        except Exception:
            # Persist what we spent, mark the run errored, and DO NOT re-raise: letting this
            # escape `tenant_session` rolls back the ledger rows AND the status write, leaving
            # the run stuck at "queued" (which the UI reads as still-in-progress) with no trace
            # of the failure. The errored run IS the signal; the log carries the traceback.
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
            await finalize_run(session, run, _ERROR_STATS, status="error")
            _log.exception("run.discovery.failed", extra={"stage": "discovery"})


async def trigger_discovery_run(user_id: UUID, run_id: UUID) -> None:
    if settings.pipeline_execution == "inline":
        deps = build_deps(settings)
        try:
            async with tenant_session(user_id) as session:
                await run_discovery(session, user_id, run_id, deps)
        finally:
            await deps.aclose()
    else:
        # TODO(scheduler milestone): enqueue to Arq
        pass


async def run_rescore(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> None:
    """Re-score all existing postings against the current profile, wrapped in a Run for the same
    cost ledger + observability as discovery (mirrors `run_discovery`)."""
    run = await get_run(session, user_id, run_id)
    if run is None:
        return

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()

    with log_context(user_id=user_id, run_id=run_id):
        _log.info("run.rescore.start", extra={"stage": "score"})
        try:
            scored = await rescore_all(session, user_id, deps)
            stats: dict[str, object] = {
                "found": 0,
                "new": 0,
                "closed": 0,
                "low_conf_excluded": 0,
                "errors": 0,
                "scored": scored,
            }
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
            await finalize_run(session, run, stats, status="done")
            _log.info("run.rescore.done", extra={"stage": "score", "scored": scored})
        except Exception:
            # See run_discovery: swallowing is deliberate so the ledger + error status commit.
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
            await finalize_run(session, run, {**_ERROR_STATS, "scored": 0}, status="error")
            _log.exception("run.rescore.failed", extra={"stage": "score"})


async def trigger_rescore_run(user_id: UUID, run_id: UUID) -> None:
    if settings.pipeline_execution == "inline":
        deps = build_deps(settings)
        try:
            async with tenant_session(user_id) as session:
                await run_rescore(session, user_id, run_id, deps)
        finally:
            await deps.aclose()
    else:
        # TODO(scheduler milestone): enqueue to Arq
        pass


def _apply_enrichment(company: Company, enriched: EnrichResult) -> None:
    if enriched.name:
        company.name = enriched.name
    if enriched.hq_country is not None:
        company.hq_country = enriched.hq_country
    if enriched.hq_confidence is not None:
        company.hq_confidence = enriched.hq_confidence
    if enriched.comp_estimate is not None:
        company.comp_estimate = enriched.comp_estimate
    # Only FILL a missing careers_url, never overwrite. Discovery's URL is observed fact;
    # the model's is a guess, and letting it win would discard the real one permanently —
    # every later run would then enrich from the guess.
    if company.careers_url is None and enriched.careers_url is not None:
        company.careers_url = enriched.careers_url
    if enriched.ats is not None:
        company.ats = enriched.ats
    if not company.logo_url and company.domain:
        company.logo_url = favicon_url(company.domain)


async def ingest_company(
    session: AsyncSession, user_id: UUID, company_id: UUID, deps: PipelineDeps
) -> None:
    """Enrich → fetch → extract → embed → dedup → score one company. Records its (dominant)
    OpenAI usage as `llm_costs` rows keyed to the company (no Run exists for an ingest); the
    `finally` drains those rows into the session on every path, but an exception escaping the
    pipeline still propagates and `tenant_session` rolls the whole ingest back — ledger rows
    included — so a crashed ingest records nothing."""
    company = await session.get(Company, company_id)
    if company is None or company.user_id != user_id or company.opt_out:
        return

    with log_context(user_id=user_id):
        _log.info("ingest.start", extra={"stage": "enrich", "company_id": str(company.id)})
        try:
            await _ingest_pipeline(session, user_id, company, deps)
            _log.info("ingest.done", extra={"company_id": str(company.id)})
        finally:
            await _persist_usage(session, user_id, deps, run_id=None, company_id=company.id)


async def _ingest_pipeline(
    session: AsyncSession, user_id: UUID, company: Company, deps: PipelineDeps
) -> None:
    enriched = await enrich_company(company, deps)
    _apply_enrichment(company, enriched)
    await session.flush()
    await fetch_postings(session, user_id, company, deps)

    needing_extraction = await session.scalars(
        select(Posting)
        .where(
            Posting.company_id == company.id,
            Posting.user_id == user_id,
            Posting.title.is_(None),
        )
        .order_by(Posting.first_seen_at.desc())
        .limit(deps.settings.ingest_max_postings)
    )
    for posting in needing_extraction:
        await extract_posting(session, posting, deps)
        if posting.title and posting.extraction_confidence:
            await embed_posting(posting, deps)

    await dedup_company(session, user_id, company.id)

    ctx = await _prepare_scoring(session, user_id, deps)
    if ctx is None:
        return
    await _score_company_postings(session, user_id, company.id, ctx, deps)


@dataclass(frozen=True)
class _ScoringContext:
    """The per-user scoring inputs, computed once and reused across every posting in a run or
    rescore: the candidate profile, targeting, and the Targeting-derived embeddings."""

    candidate: CandidateProfile
    targeting: Targeting
    role_titles_vec: list[float]
    must_have_vecs: list[list[float]]


async def _prepare_scoring(
    session: AsyncSession, user_id: UUID, deps: PipelineDeps
) -> _ScoringContext | None:
    """Load the candidate profile + targeting and embed the Targeting-derived vectors ONCE
    (role titles + must-haves), shared across every posting scored. Returns None when the user
    has no profile or targeting yet — there is nothing to score against."""
    candidate = await session.get(CandidateProfile, user_id)
    targeting = await session.get(Targeting, user_id)
    if candidate is None or targeting is None:
        return None

    await ensure_candidate_vectors(session, candidate, deps)
    [role_titles_vec] = await deps.openai.embed([" ".join(targeting.role_titles)])
    # Casefolded so a must-have compares against the CANONICAL form skill_vectors caches —
    # "Python" and the skill "python" then resolve to one vector and match at exactly 1.0
    # instead of merely being near neighbours. `must_haves` defaults to '{}', so empty is the
    # normal state for a new user. The live embeddings endpoint rejects an empty input array,
    # which would kill scoring before a single posting is scored — and the recorded client
    # can't catch it, since it loops over `texts` and returns [] for [] quite happily.
    must_have_texts = [must_have.strip().casefold() for must_have in targeting.must_haves]
    must_have_vecs = await deps.openai.embed(must_have_texts) if must_have_texts else []
    return _ScoringContext(candidate, targeting, role_titles_vec, must_have_vecs)


async def _score_company_postings(
    session: AsyncSession, user_id: UUID, company_id: UUID, ctx: _ScoringContext, deps: PipelineDeps
) -> int:
    """Score every scorable (extracted, confident) posting for one company against `ctx`, and
    return the count. `score_posting` upserts by posting_id, so this safely re-scores."""
    scorable = await session.scalars(
        select(Posting).where(
            Posting.company_id == company_id,
            Posting.user_id == user_id,
            Posting.title.is_not(None),
            Posting.extraction_confidence >= 1,
        )
    )
    count = 0
    for posting in scorable:
        await score_posting(
            session,
            user_id,
            posting,
            ctx.candidate,
            ctx.targeting,
            ctx.role_titles_vec,
            ctx.must_have_vecs,
            deps,
        )
        count += 1
    return count


async def rescore_all(session: AsyncSession, user_id: UUID, deps: PipelineDeps) -> int:
    """Re-score every existing posting against the CURRENT candidate profile + targeting — no
    crawl, no extract (the profile changed, the postings didn't). Skips opted-out companies.
    Returns the number of postings scored."""
    ctx = await _prepare_scoring(session, user_id, deps)
    if ctx is None:
        return 0
    company_ids = (
        await session.scalars(
            select(Company.id).where(Company.user_id == user_id, Company.opt_out.is_(False))
        )
    ).all()
    total = 0
    for company_id in company_ids:
        total += await _score_company_postings(session, user_id, company_id, ctx, deps)
    return total


async def trigger_company_ingest(user_id: UUID, company_id: UUID) -> None:
    if settings.pipeline_execution == "inline":
        deps = build_deps(settings)
        try:
            async with tenant_session(user_id) as session:
                await ingest_company(session, user_id, company_id, deps)
        finally:
            await deps.aclose()
    else:
        # TODO(scheduler milestone): enqueue to Arq
        pass


async def _posting_count(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(Posting).where(Posting.user_id == user_id)
        )
    ) or 0


async def refresh_all_jobs(session: AsyncSession, user_id: UUID, deps: PipelineDeps) -> int:
    """Re-crawl every tracked (non-opted-out) company for NEW postings, extracting + scoring them
    — the same per-company ingest that fires on approval, run for the whole registry at once.
    Existing postings dedup out, so this surfaces only genuinely new jobs. Returns how many new
    postings were found across all companies."""
    company_ids = (
        await session.scalars(
            select(Company.id).where(Company.user_id == user_id, Company.opt_out.is_(False))
        )
    ).all()
    before = await _posting_count(session, user_id)
    for company_id in company_ids:
        await ingest_company(session, user_id, company_id, deps)
    after = await _posting_count(session, user_id)
    return after - before


async def run_refresh(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> None:
    """Re-crawl all tracked companies for new jobs, wrapped in a Run for the same cost ledger +
    observability as discovery (mirrors `run_rescore`). Per-company ingest keys its own cost
    rows to the company."""
    run = await get_run(session, user_id, run_id)
    if run is None:
        return

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()

    with log_context(user_id=user_id, run_id=run_id):
        _log.info("run.refresh.start", extra={"stage": "fetch"})
        try:
            new = await refresh_all_jobs(session, user_id, deps)
            stats: dict[str, object] = {
                "found": 0,
                "new": new,
                "closed": 0,
                "low_conf_excluded": 0,
                "errors": 0,
                "scored": 0,
            }
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
            await finalize_run(session, run, stats, status="done")
            _log.info("run.refresh.done", extra={"stage": "fetch", "new": new})
        except Exception:
            # See run_discovery: swallowing is deliberate so the ledger + error status commit.
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
            await finalize_run(session, run, _ERROR_STATS, status="error")
            _log.exception("run.refresh.failed", extra={"stage": "fetch"})


async def trigger_refresh_run(user_id: UUID, run_id: UUID) -> None:
    if settings.pipeline_execution == "inline":
        deps = build_deps(settings)
        try:
            async with tenant_session(user_id) as session:
                await run_refresh(session, user_id, run_id, deps)
        finally:
            await deps.aclose()
    else:
        # TODO(scheduler milestone): enqueue to Arq
        pass
