import uuid
from datetime import UTC, datetime

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


DAY_A = datetime(2026, 7, 5, 12, tzinfo=UTC)
DAY_B = datetime(2026, 7, 6, 12, tzinfo=UTC)
DAY_C = datetime(2026, 7, 7, 12, tzinfo=UTC)


async def _seed(
    *,
    sub: str,
    costs: list[dict[str, object]] | None = None,
    runs: list[dict[str, object]] | None = None,
) -> uuid.UUID:
    """Create a fresh user and the given llm_costs + runs rows, committed so the API
    (a separate session, matched by google_sub) can read them under RLS. Each cost dict
    may set stage/model/prompt_tokens/completion_tokens/embed_tokens/created_at, plus
    `run` — an index into `runs` linking the row to that run (omit for ingest-style rows
    that belong to no run). Each run dict may set kind/status/duration_ms/created_at."""
    async with async_session() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=sub)
        session.add(user)
        await session.flush()
        await _set_tenant(session, user.id)

        run_models: list[Run] = []
        for spec in runs or []:
            run = Run(
                user_id=user.id,
                kind=str(spec.get("kind", "on_demand")),
                status=str(spec.get("status", "done")),
                duration_ms=spec.get("duration_ms"),
                created_at=spec.get("created_at", DAY_A),
            )
            session.add(run)
            run_models.append(run)
        await session.flush()  # assign run ids before linking cost rows

        for spec in costs or []:
            idx = spec.get("run")
            session.add(
                LlmCost(
                    user_id=user.id,
                    run_id=run_models[int(str(idx))].id if idx is not None else None,
                    stage=str(spec.get("stage", "extract")),
                    model=str(spec.get("model", "gpt-4o-mini")),
                    prompt_tokens=int(str(spec.get("prompt_tokens", 0))),
                    completion_tokens=int(str(spec.get("completion_tokens", 0))),
                    embed_tokens=int(str(spec.get("embed_tokens", 0))),
                    created_at=spec.get("created_at", DAY_A),
                )
            )
        await session.commit()
        return user.id


async def _get(path: str, sub: str) -> object:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=_auth_header(sub))


@requires_db
async def test_dashboard_empty_for_fresh_user(migrated_db: None) -> None:
    resp = await _get("/api/v1/dashboard", _sub())
    assert resp.status_code == 200  # type: ignore[attr-defined]
    body = resp.json()  # type: ignore[attr-defined]
    assert body["totalTokens"] == 0
    assert body["runCount"] == 0
    assert body["tokensByStage"] == []
    assert body["tokensByDay"] == []
    assert body["recentRuns"] == []


@requires_db
async def test_dashboard_aggregates_tokens_and_runs(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        costs=[
            {
                "stage": "extract",
                "prompt_tokens": 800,
                "completion_tokens": 200,
                "created_at": DAY_A,
            },
            {"stage": "embed", "embed_tokens": 100, "created_at": DAY_A},
            {
                "stage": "extract",
                "prompt_tokens": 400,
                "completion_tokens": 100,
                "created_at": DAY_B,
            },
            {
                "stage": "score",
                "prompt_tokens": 1500,
                "completion_tokens": 500,
                "created_at": DAY_B,
            },
        ],
        runs=[
            {"created_at": DAY_A},
            {"created_at": DAY_B},
            {"created_at": DAY_B},
        ],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]

    assert body["totalTokens"] == 3600  # 1000 + 100 + 500 + 2000
    assert body["runCount"] == 3
    assert "totalCostUsd" not in body

    # tokensByStage: summed per stage, ordered by volume desc.
    stages = body["tokensByStage"]
    assert [s["stage"] for s in stages] == ["score", "extract", "embed"]
    by_stage = {s["stage"]: s["totalTokens"] for s in stages}
    assert by_stage["extract"] == 1500
    assert by_stage["score"] == 2000
    assert by_stage["embed"] == 100

    # tokensByDay: one point per day (ascending), tokens from llm_costs, runs from runs.
    days = body["tokensByDay"]
    assert [p["date"] for p in days] == ["2026-07-05", "2026-07-06"]
    assert days[0]["totalTokens"] == 1100
    assert days[0]["runs"] == 1
    assert days[1]["totalTokens"] == 2500
    assert days[1]["runs"] == 2


@requires_db
async def test_token_day_includes_days_with_usage_but_no_run(migrated_db: None) -> None:
    # Company ingest spends LLM tokens without creating a Run (see LlmCost docstring):
    # such a day must still appear, with runs == 0.
    sub = _sub()
    await _seed(
        sub=sub,
        costs=[{"stage": "extract", "prompt_tokens": 300, "created_at": DAY_A}],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]
    assert body["runCount"] == 0
    assert body["tokensByDay"] == [{"date": "2026-07-05", "totalTokens": 300, "runs": 0}]


@requires_db
async def test_recent_runs_carry_derived_tokens_and_are_newest_first(
    migrated_db: None,
) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        runs=[
            {"kind": "scheduled", "status": "done", "duration_ms": 5555, "created_at": DAY_A},
            {"kind": "on_demand", "status": "error", "duration_ms": 1234, "created_at": DAY_B},
            {"kind": "refresh", "status": "done", "duration_ms": 4321, "created_at": DAY_C},
        ],
        # Both rows belong to run index 1 — its total is DERIVED as their sum. Run index 2's
        # only ledger row sums to exactly 0 tokens.
        costs=[
            {"stage": "discovery", "prompt_tokens": 700, "run": 1, "created_at": DAY_B},
            {"stage": "score", "completion_tokens": 300, "run": 1, "created_at": DAY_B},
            {"stage": "embed", "run": 2, "created_at": DAY_C},
        ],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]
    recent = body["recentRuns"]
    assert len(recent) == 3
    # Newest first.
    assert recent[0]["kind"] == "refresh"
    # A linked ledger row that sums to 0 tokens must still serialize {"totalTokens": 0, ...} —
    # NOT null. Null means no ledger row exists at all; distinguishing the two is exactly what
    # a future `defaultdict`/`or 0` regression would silently break.
    assert recent[0]["tokens"] == {"totalTokens": 0}
    assert recent[0]["durationMs"] == 4321
    assert recent[1]["kind"] == "on_demand"
    assert recent[1]["status"] == "error"
    assert recent[1]["tokens"]["totalTokens"] == 1000
    assert recent[1]["durationMs"] == 1234
    # A run with NO ledger rows serializes tokens as null — "nothing recorded" is
    # distinct from "recorded zero" — but its duration is a property of the RUN and survives.
    assert recent[2]["kind"] == "scheduled"
    assert recent[2]["tokens"] is None
    assert recent[2]["durationMs"] == 5555


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    owner = _sub()
    await _seed(
        sub=owner,
        costs=[{"stage": "score", "prompt_tokens": 500, "created_at": DAY_A}],
        runs=[{"created_at": DAY_A}],
    )

    body = (await _get("/api/v1/dashboard", _sub())).json()  # type: ignore[attr-defined]
    assert body["totalTokens"] == 0
    assert body["runCount"] == 0
    assert body["tokensByStage"] == []
    assert body["tokensByDay"] == []
    assert body["recentRuns"] == []
