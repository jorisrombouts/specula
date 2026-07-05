import asyncio

import pytest
import sqlalchemy as sa

from specula_api.db.session import engine


def _db_reachable() -> bool:
    async def check() -> bool:
        try:
            async with engine.connect():
                return True
        except Exception:
            return False

    try:
        return asyncio.run(check())
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_reachable(), reason="Postgres not reachable (run `just up`)"
)


@requires_db
def test_m2_schema_and_rls(migrated_db: None) -> None:
    async def check() -> None:
        async with engine.connect() as conn:
            assert (
                await conn.execute(sa.text("select to_regclass('public.lenses')"))
            ).scalar() == "lenses"
            forced = (
                await conn.execute(
                    sa.text("select relforcerowsecurity from pg_class where relname='lenses'")
                )
            ).scalar()
            assert forced is True
            ext = (
                await conn.execute(
                    sa.text(
                        "select count(*) from pg_extension where extname in ('vector','pg_trgm')"
                    )
                )
            ).scalar()
            assert ext == 2

    asyncio.run(check())
