import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import LlmCost, Run, User
from specula_api.db.session import async_session
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _sub() -> str:
    return f"test-sub-{uuid.uuid4()}"


def _auth_header(sub: str) -> dict[str, str]:
    token = mint(sub=sub, email=f"{uuid.uuid4()}@example.com", name="Test User")
    return {"Authorization": f"Bearer {token}"}


async def _set_tenant(session: object, user_id: uuid.UUID) -> None:
    await session.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
    )


async def _seed(
    *,
    sub: str,
    costs: list[dict[str, object]] | None = None,
    runs: list[dict[str, object]] | None = None,
) -> uuid.UUID:
    """Create a fresh user and the given llm_costs + runs rows, committed so the API
    (a separate session, matched by google_sub) can read them under RLS. Each cost dict
    may set stage/model/cost_usd/created_at; each run dict may set kind/status/cost_usd/
    duration_ms/created_at."""
    async with async_session() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=sub)
        session.add(user)
        await session.flush()
        await _set_tenant(session, user.id)

        for spec in costs or []:
            session.add(
                LlmCost(
                    user_id=user.id,
                    stage=str(spec.get("stage", "extract")),
                    model=str(spec.get("model", "gpt-4o-mini")),
                    cost_usd=Decimal(str(spec.get("cost_usd", "0"))),
                    created_at=spec.get("created_at", datetime(2026, 7, 5, 12, tzinfo=UTC)),
                )
            )
        for spec in runs or []:
            cost_usd = spec.get("cost_usd")
            session.add(
                Run(
                    user_id=user.id,
                    kind=str(spec.get("kind", "on_demand")),
                    status=str(spec.get("status", "done")),
                    cost_usd=Decimal(str(cost_usd)) if cost_usd is not None else None,
                    duration_ms=spec.get("duration_ms"),
                    created_at=spec.get("created_at", datetime(2026, 7, 5, 12, tzinfo=UTC)),
                )
            )
        await session.commit()
        return user.id


async def _get(path: str, sub: str) -> object:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=_auth_header(sub))


DAY_A = datetime(2026, 7, 5, 12, tzinfo=UTC)
DAY_B = datetime(2026, 7, 6, 12, tzinfo=UTC)


@requires_db
async def test_dashboard_empty_for_fresh_user(migrated_db: None) -> None:
    resp = await _get("/api/v1/dashboard", _sub())
    assert resp.status_code == 200  # type: ignore[attr-defined]
    body = resp.json()  # type: ignore[attr-defined]
    assert body["totalCostUsd"] == 0
    assert body["runCount"] == 0
    assert body["costByStage"] == []
    assert body["costByDay"] == []
    assert body["recentRuns"] == []


@requires_db
async def test_dashboard_aggregates_costs_and_runs(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        costs=[
            {"stage": "extract", "cost_usd": "0.10", "created_at": DAY_A},
            {"stage": "embed", "cost_usd": "0.02", "created_at": DAY_A},
            {"stage": "extract", "cost_usd": "0.05", "created_at": DAY_B},
            {"stage": "score", "cost_usd": "0.20", "created_at": DAY_B},
        ],
        runs=[
            {"created_at": DAY_A},
            {"created_at": DAY_B},
            {"created_at": DAY_B},
        ],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]

    assert body["totalCostUsd"] == pytest.approx(0.37)
    assert body["runCount"] == 3

    # costByStage: summed per stage, ordered by spend desc.
    stages = body["costByStage"]
    assert [s["stage"] for s in stages] == ["score", "extract", "embed"]
    by_stage = {s["stage"]: s["costUsd"] for s in stages}
    assert by_stage["extract"] == pytest.approx(0.15)
    assert by_stage["score"] == pytest.approx(0.20)
    assert by_stage["embed"] == pytest.approx(0.02)

    # costByDay: one point per day (ascending), cost from llm_costs, runs from runs.
    days = body["costByDay"]
    assert [p["date"] for p in days] == ["2026-07-05", "2026-07-06"]
    assert days[0]["costUsd"] == pytest.approx(0.12)
    assert days[0]["runs"] == 1
    assert days[1]["costUsd"] == pytest.approx(0.25)
    assert days[1]["runs"] == 2


@requires_db
async def test_cost_day_includes_days_with_costs_but_no_run(migrated_db: None) -> None:
    # Company ingest spends LLM tokens without creating a Run (see LlmCost docstring):
    # such a day must still appear, with runs == 0.
    sub = _sub()
    await _seed(sub=sub, costs=[{"stage": "extract", "cost_usd": "0.03", "created_at": DAY_A}])

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]
    assert body["runCount"] == 0
    assert body["costByDay"] == [{"date": "2026-07-05", "costUsd": pytest.approx(0.03), "runs": 0}]


@requires_db
async def test_recent_runs_carry_cost_and_are_newest_first(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        runs=[
            {"kind": "scheduled", "status": "done", "created_at": DAY_A},
            {
                "kind": "on_demand",
                "status": "error",
                "cost_usd": "0.30",
                "duration_ms": 1234,
                "created_at": DAY_B,
            },
        ],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]
    recent = body["recentRuns"]
    assert len(recent) == 2
    # Newest first.
    assert recent[0]["kind"] == "on_demand"
    assert recent[0]["status"] == "error"
    assert recent[0]["cost"]["costUsd"] == pytest.approx(0.30)
    assert recent[0]["cost"]["durationMs"] == 1234
    # A run without a cost rollup serializes cost as null.
    assert recent[1]["kind"] == "scheduled"
    assert recent[1]["cost"] is None


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    owner = _sub()
    await _seed(
        sub=owner,
        costs=[{"stage": "score", "cost_usd": "0.50", "created_at": DAY_A}],
        runs=[{"created_at": DAY_A}],
    )

    body = (await _get("/api/v1/dashboard", _sub())).json()  # type: ignore[attr-defined]
    assert body["totalCostUsd"] == 0
    assert body["runCount"] == 0
    assert body["costByStage"] == []
    assert body["costByDay"] == []
    assert body["recentRuns"] == []
