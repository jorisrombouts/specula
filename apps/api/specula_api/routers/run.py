from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.ratelimit import RateLimitedRoute, rate_limit_guard
from specula_api.schemas.run import RunOut
from specula_api.services.run import create_run, get_run, latest_run, trigger_discovery_run

router = APIRouter(prefix="/runs", tags=["runs"], route_class=RateLimitedRoute)


@router.post("", status_code=201)
async def start_run(
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    _: None = Depends(rate_limit_guard),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    run = await create_run(session, user_id)
    out = RunOut.from_model(run)
    # get_session's post-yield commit doesn't run until after the response
    # (including BackgroundTasks) has been sent — FastAPI's dependency
    # AsyncExitStack now outlives the response to support streaming responses.
    # Commit explicitly so the row is durably visible to the background task's
    # own tenant_session connection before it starts.
    await session.commit()
    background_tasks.add_task(trigger_discovery_run, user_id, run.id)
    return out


@router.get("/latest")
async def read_latest_run(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> RunOut | None:
    run = await latest_run(session, user_id)
    if run is None:
        return None
    return RunOut.from_model(run)


@router.get("/{run_id}")
async def read_run(
    run_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    run = await get_run(session, user_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut.from_model(run)
