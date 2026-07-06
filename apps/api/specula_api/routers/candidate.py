from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.candidate import CandidateIn, CandidateOut
from specula_api.services.candidate import get_candidate, upsert_candidate

router = APIRouter(prefix="/candidate", tags=["candidate"])


@router.get("")
async def read_candidate(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CandidateOut:
    candidate = await get_candidate(session, user_id)
    if candidate is None:
        return CandidateOut(updated_at=datetime.now(UTC))
    return CandidateOut.model_validate(candidate)


@router.put("")
async def replace_candidate(
    data: CandidateIn,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CandidateOut:
    candidate = await upsert_candidate(session, user_id, data)
    return CandidateOut.model_validate(candidate)
