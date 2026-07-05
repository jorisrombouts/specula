from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.db.models import Targeting


@requires_db
async def test_user_a_cannot_see_user_b_rows(db_session: AsyncSession) -> None:
    a = await make_user(db_session)
    b = await make_user(db_session)

    await set_tenant(db_session, a.id)
    db_session.add(Targeting(user_id=a.id, role_titles=["ML Eng"]))
    await db_session.flush()

    await set_tenant(db_session, b.id)
    rows = (await db_session.scalars(select(Targeting))).all()
    assert rows == []

    await set_tenant(db_session, a.id)
    assert len((await db_session.scalars(select(Targeting))).all()) == 1
