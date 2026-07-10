import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from specula_api.config import settings
from specula_api.db import models  # noqa: F401  (register models on Base.metadata)
from specula_api.db.models import User
from specula_api.db.session import engine
from specula_api.pipeline.deps import DEFAULT_FIXTURES_DIR


@pytest.fixture(scope="session")
def migrated_db() -> None:
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def _recorded_pipeline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Settings.pipeline_mode` defaults to "live" in production. Tests must never hit
    real OpenAI/network, so force the settings singleton `build_deps` reads (see
    services/run.py's `trigger_discovery_run`/`trigger_company_ingest`) to "recorded" for
    the whole test run — this makes every test that triggers a run resolve deterministically
    to `RecordedOpenAIClient`/`RecordedFetcher` against `tests/fixtures/pipeline`."""
    monkeypatch.setattr(settings, "pipeline_mode", "recorded")
    monkeypatch.setattr(settings, "pipeline_fixtures_dir", str(DEFAULT_FIXTURES_DIR))


@pytest_asyncio.fixture
async def db_session(migrated_db: None) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


async def set_tenant(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
    )


async def make_user(session: AsyncSession) -> User:
    u = User(email=f"{uuid.uuid4()}@example.com", google_sub=str(uuid.uuid4()))
    session.add(u)
    await session.flush()
    return u
