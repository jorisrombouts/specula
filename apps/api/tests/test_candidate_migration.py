from sqlalchemy import text
from test_db import requires_db

from specula_api.db.session import async_session

# NOTE: reversibility is verified MANUALLY (`just migrate-down` then `just migrate`), not in
# this suite. An in-suite `alembic downgrade/upgrade` round-trip is a WHOLE-TABLE transform
# that runs against the shared dev DB (tests use settings.database_url; there is no separate
# test database), so it lossily corrupts every real candidate row on each run — it once
# mangled the seeded demo profile. Do not reintroduce a down/up test here.


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
