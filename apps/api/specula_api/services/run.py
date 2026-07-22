from datetime import UTC, datetime
from decimal import Decimal
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
from specula_api.pipeline.openai_client import BudgetExceeded, EnrichResult
from specula_api.pipeline.score import ensure_candidate_vectors, score_posting
from specula_api.pipeline.util import favicon_url

_log = get_logger("pipeline.run")


async def _seed_daily_baseline(session: AsyncSession, user_id: UUID, deps: PipelineDeps) -> None:
    """Load the user's OpenAI spend earlier today into the sink, so the per-day ceiling spans
    every run today, not just this one. No-op when metering is off (hand-built deps)."""
    sink = deps.cost_sink
    if sink is None:
        return
    start_of_day = deps.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total = await session.scalar(
        select(func.coalesce(func.sum(LlmCost.cost_usd), 0)).where(
            LlmCost.user_id == user_id, LlmCost.created_at >= start_of_day
        )
    )
    sink.daily_baseline = Decimal(total or 0)


async def _persist_costs(
    session: AsyncSession,
    user_id: UUID,
    deps: PipelineDeps,
    *,
    run_id: UUID | None,
    company_id: UUID | None,
) -> Decimal:
    """Drain the cost sink into `llm_costs` rows (one per metered call) and return their total.
    Company ingest creates no Run, so its rows carry `run_id=None, company_id=<id>` (OBS→DASH
    contract). Draining makes this safe to call once per run/ingest without double-counting."""
    sink = deps.cost_sink
    if sink is None:
        return Decimal("0")
    created_at = deps.now()
    total = Decimal("0")
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
                cost_usd=record.cost_usd,
                created_at=created_at,
            )
        )
        total += record.cost_usd
    sink.records.clear()
    await session.flush()
    return total


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
    run: Run | None = await session.scalar(
        select(Run).where(Run.user_id == user_id).order_by(Run.created_at.desc()).limit(1)
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
    await _seed_daily_baseline(session, user_id, deps)

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
            run.cost_usd = await _persist_costs(
                session, user_id, deps, run_id=run_id, company_id=None
            )
            await finalize_run(session, run, stats, status="done")
            _log.info("run.discovery.done", extra={"stage": "discovery"})
        except BudgetExceeded as exc:
            # Persist what we already spent, mark the run errored, and DO NOT re-raise: letting
            # the abort escape tenant_session would roll the ledger rows back.
            run.cost_usd = await _persist_costs(
                session, user_id, deps, run_id=run_id, company_id=None
            )
            await finalize_run(session, run, _ERROR_STATS, status="error")
            _log.warning("run.budget_exceeded", extra={"stage": "discovery", "scope": exc.scope})
        except Exception:
            await finalize_run(session, run, _ERROR_STATS, status="error")
            raise


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


def _apply_enrichment(company: Company, enriched: EnrichResult) -> None:
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
    OpenAI spend as `llm_costs` rows keyed to the company (no Run exists for an ingest), and
    aborts cleanly on a budget breach — costs already accrued are still persisted (finally)."""
    company = await session.get(Company, company_id)
    if company is None or company.user_id != user_id or company.opt_out:
        return

    await _seed_daily_baseline(session, user_id, deps)
    with log_context(user_id=user_id):
        _log.info("ingest.start", extra={"stage": "enrich", "company_id": str(company.id)})
        try:
            await _ingest_pipeline(session, user_id, company, deps)
            _log.info("ingest.done", extra={"company_id": str(company.id)})
        except BudgetExceeded as exc:
            # Swallow the abort so the ledger + partial work commit (see run_discovery).
            _log.warning(
                "ingest.budget_exceeded",
                extra={"scope": exc.scope, "company_id": str(company.id)},
            )
        finally:
            await _persist_costs(session, user_id, deps, run_id=None, company_id=company.id)


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

    candidate = await session.get(CandidateProfile, user_id)
    targeting = await session.get(Targeting, user_id)
    if candidate is None or targeting is None:
        return

    await ensure_candidate_vectors(session, candidate, deps)
    [role_titles_vec] = await deps.openai.embed([" ".join(targeting.role_titles)])
    # Per-run constants derived from Targeting, embedded once here rather than per posting
    # (same reason as role_titles_vec above). Casefolded so a must-have compares against the
    # CANONICAL form skill_vectors caches — "Python" and the skill "python" then resolve to
    # one vector and match at exactly 1.0 instead of merely being near neighbours.
    # `must_haves` defaults to '{}', so empty is the normal state for a new user. The live
    # embeddings endpoint rejects an empty input array, which would kill the run before a
    # single posting is scored — and the recorded client can't catch it, since it loops over
    # `texts` and returns [] for [] quite happily.
    must_have_texts = [must_have.strip().casefold() for must_have in targeting.must_haves]
    must_have_vecs = await deps.openai.embed(must_have_texts) if must_have_texts else []

    scorable = await session.scalars(
        select(Posting).where(
            Posting.company_id == company.id,
            Posting.user_id == user_id,
            Posting.title.is_not(None),
            Posting.extraction_confidence >= 1,
        )
    )
    for posting in scorable:
        await score_posting(
            session, user_id, posting, candidate, targeting, role_titles_vec, must_have_vecs, deps
        )


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
