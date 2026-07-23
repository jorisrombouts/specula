from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Targeting
from specula_api.schemas.targeting import TargetingIn


async def get_targeting(session: AsyncSession, user_id: UUID) -> Targeting | None:
    return await session.get(Targeting, user_id)


async def upsert_targeting(session: AsyncSession, user_id: UUID, data: TargetingIn) -> Targeting:
    targeting = await session.get(Targeting, user_id)
    if targeting is None:
        targeting = Targeting(user_id=user_id)
        session.add(targeting)

    for field, value in data.model_dump().items():
        setattr(targeting, field, value)

    await session.flush()
    # updated_at is DB-managed (server onupdate); refresh it inside the async greenlet so the
    # response model can read it without a lazy load (MissingGreenlet on the UPDATE path).
    await session.refresh(targeting, ["updated_at"])
    return targeting
