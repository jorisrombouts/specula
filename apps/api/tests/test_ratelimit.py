"""Rate-limit gate (NET lane).

Two layers under test:
- the pure in-process limiter (`_InProcessLimiter.check`) with an injected `now`, and
- the gate wired through real HTTP on `POST /runs` and the approve->ingest trigger.
"""

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_db import requires_db

from specula_api import ratelimit
from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import Approval, User
from specula_api.db.session import async_session
from specula_api.main import create_app
from specula_api.ratelimit import RateLimited, _InProcessLimiter

_WINDOW_S = 3600.0


def _uid() -> uuid.UUID:
    return uuid.uuid4()


# --- pure limiter -------------------------------------------------------------


def test_first_trigger_is_allowed() -> None:
    limiter = _InProcessLimiter()
    limiter.check(_uid(), per_hour=10, cooldown_s=60, now=0.0)  # does not raise


def test_second_trigger_inside_cooldown_is_limited() -> None:
    limiter = _InProcessLimiter()
    user = _uid()
    limiter.check(user, per_hour=10, cooldown_s=60, now=0.0)
    with pytest.raises(RateLimited) as exc:
        limiter.check(user, per_hour=10, cooldown_s=60, now=10.0)
    # 60s cooldown, 10s elapsed -> ~50s remaining, rounded up.
    assert exc.value.retry_after_s == 50


def test_trigger_after_cooldown_is_allowed() -> None:
    limiter = _InProcessLimiter()
    user = _uid()
    limiter.check(user, per_hour=10, cooldown_s=60, now=0.0)
    limiter.check(user, per_hour=10, cooldown_s=60, now=60.0)  # exactly at the boundary


def test_hourly_cap_limits_the_next_trigger() -> None:
    limiter = _InProcessLimiter()
    user = _uid()
    # cooldown 0 isolates the hourly cap: fire per_hour triggers 1s apart, all allowed.
    for i in range(3):
        limiter.check(user, per_hour=3, cooldown_s=0, now=float(i))
    with pytest.raises(RateLimited) as exc:
        limiter.check(user, per_hour=3, cooldown_s=0, now=3.0)
    # oldest hit at t=0 falls out of the window at t=3600 -> ~3597s to wait.
    assert exc.value.retry_after_s == pytest.approx(3597, abs=1)


def test_window_eviction_refreshes_budget() -> None:
    limiter = _InProcessLimiter()
    user = _uid()
    for i in range(3):
        limiter.check(user, per_hour=3, cooldown_s=0, now=float(i))
    # Advance past the window: the three old hits are evicted, so a new one is allowed.
    limiter.check(user, per_hour=3, cooldown_s=0, now=_WINDOW_S + 1)


def test_retry_after_is_at_least_one_second() -> None:
    limiter = _InProcessLimiter()
    user = _uid()
    limiter.check(user, per_hour=10, cooldown_s=60, now=0.0)
    with pytest.raises(RateLimited) as exc:
        limiter.check(user, per_hour=10, cooldown_s=60, now=59.9)
    assert exc.value.retry_after_s >= 1  # never 0 — a 0 tells a client to retry instantly


def test_limits_are_per_user() -> None:
    limiter = _InProcessLimiter()
    a, b = _uid(), _uid()
    limiter.check(a, per_hour=1, cooldown_s=60, now=0.0)
    # a is now capped, but b has its own independent bucket.
    with pytest.raises(RateLimited):
        limiter.check(a, per_hour=1, cooldown_s=60, now=1.0)
    limiter.check(b, per_hour=1, cooldown_s=60, now=1.0)  # b unaffected


# --- run vs ingest buckets ----------------------------------------------------


def test_ingest_gate_has_no_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Approvals must not be throttled by a cooldown — two ingests at the same instant both
    pass (a run would 429 on the second)."""
    ratelimit._limiter.clear()
    monkeypatch.setattr(settings, "ingest_rate_limit_per_hour", 100)
    monkeypatch.setattr(ratelimit, "_clock", lambda: 100.0)  # frozen: same instant
    user = _uid()
    ratelimit.enforce_ingest_rate_limit(user)
    ratelimit.enforce_ingest_rate_limit(user)  # no cooldown -> does not raise


def test_run_and_ingest_are_separate_buckets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs and ingests have independent budgets — recently hitting Refresh must not block
    approving companies, and each is capped on its own."""
    ratelimit._limiter.clear()
    monkeypatch.setattr(settings, "run_rate_limit_per_hour", 1)
    monkeypatch.setattr(settings, "run_cooldown_s", 0)
    monkeypatch.setattr(settings, "ingest_rate_limit_per_hour", 1)
    monkeypatch.setattr(ratelimit, "_clock", lambda: 0.0)
    user = _uid()
    ratelimit.enforce_rate_limit(user)  # spends the run budget
    ratelimit.enforce_ingest_rate_limit(user)  # ingest bucket is independent -> allowed
    with pytest.raises(RateLimited):
        ratelimit.enforce_rate_limit(user)  # run bucket now capped
    with pytest.raises(RateLimited):
        ratelimit.enforce_ingest_rate_limit(user)  # ingest bucket capped on its own (cap=1)


# --- gate through real HTTP ---------------------------------------------------


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    """The gate's limiter is a process-global singleton; clear it so per-test triggers start
    from an empty bucket regardless of order."""
    ratelimit._limiter.clear()


def _auth_header() -> dict[str, str]:
    token = mint(sub=f"test-sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.com", name="T")
    return {"Authorization": f"Bearer {token}"}


def _assert_rate_limit_body(response: Any) -> None:
    """The 429 body must match the frozen `RateLimitError` TS shape exactly (no `detail` wrap)."""
    assert response.status_code == 429
    body = response.json()
    assert body["error"] == "rate_limited"
    assert isinstance(body["retryAfterS"], int)
    assert body["retryAfterS"] >= 1
    assert set(body) == {"error", "retryAfterS"}
    assert response.headers.get("Retry-After") == str(body["retryAfterS"])


@requires_db
async def test_post_runs_over_hourly_cap_returns_rate_limit_error(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "run_rate_limit_per_hour", 2)
    monkeypatch.setattr(settings, "run_cooldown_s", 0)  # isolate the hourly cap
    headers = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/v1/runs", headers=headers)).status_code == 201
        assert (await client.post("/api/v1/runs", headers=headers)).status_code == 201
        third = await client.post("/api/v1/runs", headers=headers)

    _assert_rate_limit_body(third)


@requires_db
async def test_post_runs_inside_cooldown_returns_429(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "run_rate_limit_per_hour", 100)  # isolate the cooldown
    monkeypatch.setattr(settings, "run_cooldown_s", 60)
    headers = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/v1/runs", headers=headers)).status_code == 201
        second = await client.post("/api/v1/runs", headers=headers)

    _assert_rate_limit_body(second)
    assert second.json()["retryAfterS"] <= 60


@requires_db
async def test_post_runs_after_cooldown_is_allowed(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "run_rate_limit_per_hour", 100)
    monkeypatch.setattr(settings, "run_cooldown_s", 60)
    fake_now = [0.0]
    monkeypatch.setattr(ratelimit, "_clock", lambda: fake_now[0])
    headers = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/v1/runs", headers=headers)).status_code == 201
        fake_now[0] = 61.0  # advance past the cooldown
        after = await client.post("/api/v1/runs", headers=headers)

    assert after.status_code == 201


@requires_db
async def test_rate_limit_is_per_tenant(migrated_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "run_rate_limit_per_hour", 1)
    monkeypatch.setattr(settings, "run_cooldown_s", 0)
    headers_a = _auth_header()
    headers_b = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/v1/runs", headers=headers_a)).status_code == 201
        # A is now capped...
        _assert_rate_limit_body(await client.post("/api/v1/runs", headers=headers_a))
        # ...but B has its own budget.
        assert (await client.post("/api/v1/runs", headers=headers_b)).status_code == 201


# --- approve->ingest trigger --------------------------------------------------

_LIGHTHOUSE = {
    "name": "Lighthouse",
    "domain": "lighthouse.app",
    "logo_url": "https://icons.duckduckgo.com/ip3/lighthouse.app.ico",
    "ats": "greenhouse",
    "hq_country": "NL",
    "careers_url": "https://boards.greenhouse.io/lighthouse",
    "found_query": "ml amsterdam",
    "why": "NL ML team.",
    "open_roles": 3,
    "hq_confidence": 90,
    "decision": None,
}


async def _seed_user_with_approvals(sub: str, email: str, rows: list[dict[str, Any]]) -> None:
    async with async_session() as session:
        user = User(google_sub=sub, email=email, name="T")
        session.add(user)
        await session.flush()
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)").bindparams(u=str(user.id))
        )
        for row in rows:
            session.add(Approval(user_id=user.id, **row))
        await session.commit()


@requires_db
async def test_approve_ingest_trigger_is_capped_hourly(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Approvals have their own hourly cap (the ingest bucket) — still bounded so a burst of
    approvals can't fire unlimited crawl+LLM passes."""
    monkeypatch.setattr(settings, "ingest_rate_limit_per_hour", 1)
    sub, email = f"test-sub-{uuid.uuid4()}", f"{uuid.uuid4()}@example.com"
    await _seed_user_with_approvals(
        sub, email, [_LIGHTHOUSE, {**_LIGHTHOUSE, "domain": "second.example"}]
    )
    headers = {"Authorization": f"Bearer {mint(sub=sub, email=email, name='T')}"}

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = (await client.get("/api/v1/approvals", headers=headers)).json()
        first, second = listed[0]["id"], listed[1]["id"]
        # First approve consumes the only ingest trigger for the hour.
        ok = await client.post(
            f"/api/v1/approvals/{first}/decision", json={"decision": "approve"}, headers=headers
        )
        assert ok.status_code == 200
        # Second approve would trigger another ingest -> gated by the ingest hourly cap.
        limited = await client.post(
            f"/api/v1/approvals/{second}/decision", json={"decision": "approve"}, headers=headers
        )

    _assert_rate_limit_body(limited)


@requires_db
async def test_reject_decision_is_not_rate_limited(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate covers the approve->ingest trigger only — a cheap reject must never be limited,
    even after the trigger budget is spent."""
    monkeypatch.setattr(settings, "run_rate_limit_per_hour", 1)
    monkeypatch.setattr(settings, "run_cooldown_s", 0)
    sub, email = f"test-sub-{uuid.uuid4()}", f"{uuid.uuid4()}@example.com"
    await _seed_user_with_approvals(
        sub, email, [_LIGHTHOUSE, {**_LIGHTHOUSE, "domain": "second.example"}]
    )
    headers = {"Authorization": f"Bearer {mint(sub=sub, email=email, name='T')}"}

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = (await client.get("/api/v1/approvals", headers=headers)).json()
        first, second = listed[0]["id"], listed[1]["id"]
        # Spend the one trigger on an approve...
        assert (
            await client.post(
                f"/api/v1/approvals/{first}/decision",
                json={"decision": "approve"},
                headers=headers,
            )
        ).status_code == 200
        # ...a reject afterwards is still allowed.
        rejected = await client.post(
            f"/api/v1/approvals/{second}/decision", json={"decision": "reject"}, headers=headers
        )

    assert rejected.status_code == 200
