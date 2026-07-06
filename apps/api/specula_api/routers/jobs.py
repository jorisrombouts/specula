from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.jobs import JobOut, JobsResponseOut, JobStateIn, JobStateOut
from specula_api.services.jobs import get_job, list_jobs, upsert_state

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def read_jobs(
    lens: str | None = None,
    sort: str = "match",
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> JobsResponseOut:
    # list_jobs normalizes an unknown sort to "match" (and echoes the normalized value).
    return await list_jobs(session, user_id, lens, sort)


@router.get("/{job_id}")
async def read_job(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    job = await get_job(session, user_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}/state")
async def patch_job_state(
    job_id: UUID,
    data: JobStateIn,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> JobStateOut:
    state = await upsert_state(session, user_id, job_id, data)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state
