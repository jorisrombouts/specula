import asyncio
import uuid

from alembic.config import Config
from sqlalchemy import text
from test_db import requires_db

from alembic import command
from specula_api.db.models import CandidateProfile, User
from specula_api.db.session import async_session, tenant_session


@requires_db
async def test_candidate_profiles_column_types(migrated_db: None) -> None:
    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = 'candidate_profiles'"
                )
            )
        ).all()
    types = {name: dtype for name, dtype in rows}  # noqa: C416 (dict() breaks mypy on Row unpacking)
    assert types["work_mode"] == "ARRAY"
    assert types["languages"] == "jsonb"
    assert types["education"] == "jsonb"
    assert types["experience"] == "jsonb"


@requires_db
async def test_candidate_structured_fields_migration_round_trip(migrated_db: None) -> None:
    """upgrade -> downgrade -> upgrade on a seeded NEW-shape row: the row survives, and every
    field the (lossy) downgrade can still represent comes back intact. `migrated_db` only runs
    `alembic upgrade head` once per test session, so this test drives the actual down/up
    itself; the try/finally guarantees `upgrade head` always runs — even if an assertion
    fails — so the shared test DB is never left downgraded for sibling tests.

    Fields the downgrade is lossy for (language `level`, education `degree`/`institution`/
    `year`) are blanked by design and are deliberately NOT asserted here. `work_mode`'s
    multiple values collapse into one comma-joined element going down and re-wrap as a
    single-element array coming back up — both original words survive, just no longer as
    separate array elements, so that shape (not element-for-element equality with the
    original) is what's asserted.
    """
    cfg = Config("alembic.ini")
    user = User(email=f"{uuid.uuid4()}@example.com", google_sub=f"test-sub-{uuid.uuid4()}")
    async with async_session() as s:
        s.add(user)
        await s.commit()

    try:
        async with tenant_session(user.id) as s:
            s.add(
                CandidateProfile(
                    user_id=user.id,
                    work_mode=["Remote", "Hybrid"],
                    languages=[{"language": "English", "level": "C2"}],
                    education=[
                        {"degree": "MSc", "field": "AI", "institution": "UvA", "year": 2019}
                    ],
                    experience=[
                        {"role": "Eng", "org": "Acme", "start_year": 2020, "end_year": None}
                    ],
                )
            )

        await asyncio.to_thread(command.downgrade, cfg, "-1")
        await asyncio.to_thread(command.upgrade, cfg, "head")

        async with tenant_session(user.id) as s:
            row = await s.get(CandidateProfile, user.id)
            assert row is not None
            assert row.work_mode == ["Remote, Hybrid"]
            assert row.languages == [{"language": "English", "level": ""}]
            assert row.education == [{"degree": "", "field": "AI", "institution": "", "year": None}]
            assert row.experience == [
                {"role": "Eng", "org": "Acme", "start_year": 2020, "end_year": None}
            ]
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")  # always leave the DB at head
        async with async_session() as s:
            await s.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user.id)})
            await s.commit()
