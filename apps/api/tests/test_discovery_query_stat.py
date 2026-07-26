from datetime import UTC, datetime, timedelta
from uuid import uuid4

from conftest import make_user, set_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db
from test_discovery import _deps, _StubOpenAI

from specula_api.db.models import DiscoveryQueryStat, Lens, Targeting
from specula_api.pipeline.discovery import discover
from specula_api.pipeline.openai_client import Source

# _deps' clock is frozen here, so stat.last_run_at offsets are relative to this.
_NOW = datetime(2026, 7, 5, tzinfo=UTC)
_ROLE_Q = "ML Engineer jobs Spain"


async def _seed(session: AsyncSession, user_id: object, *, seeds: list[str]) -> None:
    session.add(Targeting(user_id=user_id, role_titles=["ML Engineer"]))
    session.add(Lens(user_id=user_id, name="Spain", seeds=seeds, scope="ES", active=True))
    await session.flush()


def _searched(openai: _StubOpenAI) -> set[str]:
    return {q for call in openai.calls for q in call}


@requires_db
async def test_exhausted_role_query_is_skipped(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    await _seed(db_session, user.id, seeds=[])
    db_session.add(
        DiscoveryQueryStat(
            user_id=user.id,
            query=_ROLE_Q,
            consecutive_empty_runs=2,  # played out
            last_run_at=_NOW - timedelta(days=1),  # within cooldown
        )
    )
    await db_session.flush()

    openai = _StubOpenAI({})
    await discover(db_session, user.id, uuid4(), _deps(openai))

    assert _ROLE_Q not in _searched(openai)  # parked — never searched
    assert openai.calls == []  # no seeds either, so nothing ran (0 cost)


@requires_db
async def test_exhausted_query_retries_after_cooldown(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    await _seed(db_session, user.id, seeds=[])
    db_session.add(
        DiscoveryQueryStat(
            user_id=user.id,
            query=_ROLE_Q,
            consecutive_empty_runs=5,
            last_run_at=_NOW - timedelta(days=8),  # cooldown lapsed → retry
        )
    )
    await db_session.flush()

    openai = _StubOpenAI({})
    await discover(db_session, user.id, uuid4(), _deps(openai))

    assert _ROLE_Q in _searched(openai)  # ran again


@requires_db
async def test_seed_runs_even_when_marked_exhausted(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    await _seed(db_session, user.id, seeds=["fintech ML Madrid"])
    db_session.add(
        DiscoveryQueryStat(
            user_id=user.id,
            query="fintech ML Madrid",
            consecutive_empty_runs=9,
            last_run_at=_NOW,
        )
    )
    await db_session.flush()

    openai = _StubOpenAI({})
    await discover(db_session, user.id, uuid4(), _deps(openai))

    assert "fintech ML Madrid" in _searched(openai)  # user seeds are never parked


@requires_db
async def test_stats_reset_on_new_then_increment_on_empty(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    await _seed(db_session, user.id, seeds=[])
    sources = {_ROLE_Q: [Source(url="https://boards.greenhouse.io/acme/jobs/1", title="x")]}

    # Run 1: finds a new company → empty-streak resets to 0.
    await discover(db_session, user.id, uuid4(), _deps(_StubOpenAI(sources)))
    stat = await db_session.get(DiscoveryQueryStat, (user.id, _ROLE_Q))
    assert stat is not None
    assert stat.consecutive_empty_runs == 0
    assert stat.last_run_at == _NOW

    # Run 2: same company (already known → 0 new) → empty-streak increments.
    await discover(db_session, user.id, uuid4(), _deps(_StubOpenAI(sources)))
    await db_session.refresh(stat)
    assert stat.consecutive_empty_runs == 1
