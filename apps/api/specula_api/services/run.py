from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import settings
from specula_api.db.models import Run
from specula_api.db.session import tenant_session


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


async def _discover_stub(session: AsyncSession, user_id: UUID, run_id: UUID) -> dict[str, object]:
    # TODO(discover task): replace with pipeline.discovery.discover
    return {"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 0}


async def run_discovery(session: AsyncSession, user_id: UUID, run_id: UUID) -> None:
    run = await get_run(session, user_id, run_id)
    if run is None:
        return

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()

    try:
        stats = await _discover_stub(session, user_id, run_id)
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
        async with tenant_session(user_id) as session:
            await run_discovery(session, user_id, run_id)
    else:
        # TODO(scheduler milestone): enqueue to Arq
        pass
