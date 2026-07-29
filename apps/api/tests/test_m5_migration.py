import uuid

from sqlalchemy import text
from test_db import requires_db

from specula_api.db.session import async_session


@requires_db
async def test_llm_costs_rls_fails_closed_without_guc(migrated_db: None) -> None:
    # No app.user_id set → RLS returns zero rows (fail-closed), never raises.
    async with async_session() as s:
        rows = (await s.execute(text("SELECT * FROM llm_costs"))).all()
        assert rows == []


@requires_db
async def test_llm_costs_scoped_by_tenant(migrated_db: None) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    async with async_session() as s:
        # seed two users so the FK holds
        for u in (a, b):
            await s.execute(
                text("INSERT INTO users (id, google_sub, email) VALUES (:i,:g,:e)"),
                {"i": str(u), "g": str(u), "e": f"{u}@x.io"},
            )
        await s.execute(text("SELECT set_config('app.user_id', :u, false)"), {"u": str(a)})
        await s.execute(
            text("INSERT INTO llm_costs (user_id, stage, model) VALUES (:u,'score','gpt-4o-mini')"),
            {"u": str(a)},
        )
        await s.commit()
    async with async_session() as s:
        await s.execute(text("SELECT set_config('app.user_id', :u, false)"), {"u": str(b)})
        assert (await s.execute(text("SELECT * FROM llm_costs"))).all() == []  # B sees none of A's
