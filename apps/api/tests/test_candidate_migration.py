from sqlalchemy import text
from test_db import requires_db

from specula_api.db.session import async_session


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
