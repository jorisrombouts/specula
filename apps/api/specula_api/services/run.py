from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import settings
from specula_api.db.models import Company, Run
from specula_api.db.session import tenant_session
from specula_api.pipeline.deps import PipelineDeps, build_deps
from specula_api.pipeline.discovery import discover
from specula_api.pipeline.enrich import enrich_company
from specula_api.pipeline.fetch import fetch_postings
from specula_api.pipeline.openai_client import EnrichResult
from specula_api.pipeline.util import favicon_url


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
    run.stats = stats
    await session.flush()


async def run_discovery(
    session: AsyncSession, user_id: UUID, run_id: UUID, deps: PipelineDeps
) -> None:
    run = await get_run(session, user_id, run_id)
    if run is None:
        return

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()

    try:
        result = await discover(session, user_id, run_id, deps)
        stats: dict[str, object] = {
            "found": result.found,
            "new": result.new,
            "closed": 0,
            "low_conf_excluded": 0,
            "errors": result.errors,
        }
        await finalize_run(session, run, stats, status="done")
    except Exception:
        await finalize_run(
            session,
            run,
            {"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 1},
            status="error",
        )
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
    if enriched.careers_url is not None:
        company.careers_url = enriched.careers_url
    if enriched.ats is not None:
        company.ats = enriched.ats
    if not company.logo_url and company.domain:
        company.logo_url = favicon_url(company.domain)


async def ingest_company(
    session: AsyncSession, user_id: UUID, company_id: UUID, deps: PipelineDeps
) -> None:
    company = await session.get(Company, company_id)
    if company is None or company.user_id != user_id:
        return

    enriched = await enrich_company(company, deps)
    _apply_enrichment(company, enriched)
    await session.flush()
    await fetch_postings(session, user_id, company, deps)
    # TODO(extract/score tasks): per new posting extract→embed→dedup→score


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
