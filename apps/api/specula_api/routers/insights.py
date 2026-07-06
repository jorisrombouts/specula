from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.insights import Insights, SkillsGap
from specula_api.services.insights import compute_insights, compute_skills_gap

router = APIRouter(tags=["insights"])


@router.get("/insights")
async def read_insights(
    period: str = "8w",
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Insights:
    return await compute_insights(session, user_id, period)


@router.get("/skills-gap")
async def read_skills_gap(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[SkillsGap]:
    return await compute_skills_gap(session, user_id)
