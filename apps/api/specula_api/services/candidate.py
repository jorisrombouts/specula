from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import CandidateProfile
from specula_api.schemas.candidate import CandidateIn


async def get_candidate(session: AsyncSession, user_id: UUID) -> CandidateProfile | None:
    return await session.get(CandidateProfile, user_id)


async def upsert_candidate(
    session: AsyncSession, user_id: UUID, data: CandidateIn
) -> CandidateProfile:
    candidate = await session.get(CandidateProfile, user_id)
    if candidate is None:
        candidate = CandidateProfile(user_id=user_id)
        session.add(candidate)

    for field, value in data.model_dump().items():
        setattr(candidate, field, value)

    await session.flush()
    # updated_at is DB-managed (server onupdate); refresh it inside the async greenlet so the
    # response model can read it without a lazy load (MissingGreenlet on the UPDATE path).
    await session.refresh(candidate, ["updated_at"])
    return candidate
