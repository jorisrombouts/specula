import pytest
from conftest import make_user, set_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.services.run import create_run, run_discovery


@requires_db
async def test_run_discovery_transitions_queued_to_done_and_persists_stats(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    run = await create_run(db_session, user.id)
    assert run.status == "queued"

    await run_discovery(db_session, user.id, run.id)

    assert run.status == "done"
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.stats == {
        "found": 0,
        "new": 0,
        "closed": 0,
        "low_conf_excluded": 0,
        "errors": 0,
    }


@requires_db
async def test_run_discovery_error_path_sets_status_error_and_reraises(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    run = await create_run(db_session, user.id)

    async def _boom(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr("specula_api.services.run._discover_stub", _boom)

    with pytest.raises(RuntimeError):
        await run_discovery(db_session, user.id, run.id)

    assert run.status == "error"
    assert run.stats["errors"] == 1
