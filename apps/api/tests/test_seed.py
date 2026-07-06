from sqlalchemy import func, select, text
from test_db import requires_db

from specula_api.db.models import Posting, User
from specula_api.db.session import async_session
from specula_api.seed import DEMO_GOOGLE_SUB, seed


@requires_db
async def test_seed_is_idempotent_and_seeds_low_confidence_posting() -> None:
    # Run twice; the demo user and its row counts must be stable (no duplication).
    async with async_session() as session:
        await seed(session)
        await session.commit()
    async with async_session() as session:
        await seed(session)
        await session.commit()

    async with async_session() as session:
        demo_users = (
            await session.scalars(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
        ).all()
        assert len(demo_users) == 1
        uid = demo_users[0].id

        # Tenant context needed to read the FORCE-RLS'd postings.
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(uid))
        )
        posting_count = await session.scalar(select(func.count()).select_from(Posting))
        assert posting_count == 3  # stable across the two seed runs

        min_conf = await session.scalar(select(func.min(Posting.extraction_confidence)))
        assert min_conf is not None  # the low-confidence posting exists
        assert min_conf < 50
