import uuid

from sqlalchemy import delete, select
from test_db import requires_db

from specula_api.db.models import Targeting, User
from specula_api.db.session import async_session, tenant_session


@requires_db
async def test_tenant_session_enforces_rls_off_request(migrated_db: None) -> None:
    # tenant_session opens its own connections, so the owning users must be
    # actually committed (not the rollback-savepoint db_session fixture) for
    # RLS's FK-backed policies to see them off-request.
    async with async_session() as session:
        user_a = User(email=f"{uuid.uuid4()}@example.com", google_sub=str(uuid.uuid4()))
        user_b = User(email=f"{uuid.uuid4()}@example.com", google_sub=str(uuid.uuid4()))
        session.add_all([user_a, user_b])
        await session.commit()

    try:
        async with tenant_session(user_a.id) as session:
            session.add(Targeting(user_id=user_a.id, role_titles=["ML Eng"]))

        async with tenant_session(user_b.id) as session:
            rows = (await session.scalars(select(Targeting))).all()
            assert rows == []

        async with tenant_session(user_a.id) as session:
            rows = (await session.scalars(select(Targeting))).all()
            assert len(rows) == 1
    finally:
        # users has no RLS; cascades clean up the Targeting row this test committed.
        async with async_session() as session:
            await session.execute(delete(User).where(User.id.in_([user_a.id, user_b.id])))
            await session.commit()
