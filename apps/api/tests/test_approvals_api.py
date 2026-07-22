import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import Approval, Company, User
from specula_api.db.session import async_session
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _sub() -> tuple[str, str]:
    return f"test-sub-{uuid.uuid4()}", f"{uuid.uuid4()}@example.com"


def _auth_header(sub: str, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint(sub=sub, email=email, name='Test User')}"}


async def _seed_user_with_approvals(
    sub: str, email: str, approvals: list[dict[str, Any]]
) -> uuid.UUID:
    """Create the JWT user + owned approval rows (RLS tenant set for the inserts)."""
    async with async_session() as session:
        user = User(google_sub=sub, email=email, name="Test User")
        session.add(user)
        await session.flush()
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)").bindparams(u=str(user.id))
        )
        for a in approvals:
            session.add(Approval(user_id=user.id, **a))
        await session.commit()
        return user.id


async def _companies_for(user_id: uuid.UUID) -> list[Company]:
    async with async_session() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)").bindparams(u=str(user_id))
        )
        result = await session.scalars(select(Company).where(Company.user_id == user_id))
        return list(result)


_LIGHTHOUSE = {
    "name": "Lighthouse",
    "domain": "lighthouse.app",
    "logo_url": "https://icons.duckduckgo.com/ip3/lighthouse.app.ico",
    "ats": "greenhouse",
    "hq_country": "NL",
    "careers_url": "https://boards.greenhouse.io/lighthouse",
    "found_query": "machine learning amsterdam scaleup",
    "why": "NL-local ML team.",
    "open_roles": 3,
    "hq_confidence": 90,
    "decision": None,
}


@requires_db
async def test_list_returns_only_undecided_mapped_to_camelcase(migrated_db: None) -> None:
    sub, email = _sub()
    await _seed_user_with_approvals(
        sub,
        email,
        [_LIGHTHOUSE, {**_LIGHTHOUSE, "domain": "decided.example", "decision": "reject"}],
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/approvals", headers=_auth_header(sub, email))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["name"] == "Lighthouse"
    assert row["logo"] == _LIGHTHOUSE["logo_url"]
    assert row["domain"] == "lighthouse.app"
    assert row["ats"] == "greenhouse"
    assert row["hq"] == "NL"
    assert row["flag"] == "🇳🇱"
    assert row["query"] == "machine learning amsterdam scaleup"
    assert row["why"] == "NL-local ML team."
    assert row["roles"] == 3
    assert row["unverified"] is False


@requires_db
async def test_low_hq_confidence_is_surfaced_as_unverified(migrated_db: None) -> None:
    sub, email = _sub()
    await _seed_user_with_approvals(sub, email, [{**_LIGHTHOUSE, "hq_confidence": 64}])

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/approvals", headers=_auth_header(sub, email))

    assert response.json()[0]["unverified"] is True


@requires_db
async def test_approve_creates_company_and_removes_from_queue(migrated_db: None) -> None:
    sub, email = _sub()
    user_id = await _seed_user_with_approvals(sub, email, [_LIGHTHOUSE])
    headers = _auth_header(sub, email)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = (await client.get("/api/v1/approvals", headers=headers)).json()
        approval_id = listed[0]["id"]

        decide = await client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "approve"},
            headers=headers,
        )
        assert decide.status_code == 200

        after = (await client.get("/api/v1/approvals", headers=headers)).json()
        assert after == []

    companies = await _companies_for(user_id)
    assert len(companies) == 1
    company = companies[0]
    assert company.name == "Lighthouse"
    assert company.domain == "lighthouse.app"
    assert company.logo_url == _LIGHTHOUSE["logo_url"]
    assert company.ats == "greenhouse"
    assert company.hq_country == "NL"
    # Carried through so enrich fetches the REAL page instead of guessing from the domain.
    assert company.careers_url == _LIGHTHOUSE["careers_url"]


@requires_db
async def test_approve_triggers_inline_company_ingest(migrated_db: None) -> None:
    """Approving schedules trigger_company_ingest as a BackgroundTask; ASGITransport runs
    BackgroundTasks before the client call returns (see test_run_api.py), and pipeline_mode
    defaults to "recorded", so the enrichment below is deterministic — no real OpenAI/network."""
    sub, email = _sub()
    user_id = await _seed_user_with_approvals(sub, email, [_LIGHTHOUSE])
    headers = _auth_header(sub, email)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        approval_id = (await client.get("/api/v1/approvals", headers=headers)).json()[0]["id"]
        decide = await client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "approve"},
            headers=headers,
        )
        assert decide.status_code == 200

    companies = await _companies_for(user_id)
    assert len(companies) == 1
    company = companies[0]
    # Fields carried straight from the approval stay put...
    assert company.ats == "greenhouse"
    assert company.hq_country == "NL"
    # ...and enrichment fills in what the approval didn't know, from
    # tests/fixtures/pipeline/openai/enrich/lighthouse.app.json.
    assert company.hq_confidence == 92
    assert company.comp_estimate == "€70k-€95k, NL market"
    # careers_url is the exception: the approval already carried the URL discovery observed,
    # so enrichment must not replace it with the model's guess (the fixture offers
    # "https://lighthouse.app/careers"). It only fills the field when it's empty.
    assert company.careers_url == _LIGHTHOUSE["careers_url"]


@requires_db
@pytest.mark.parametrize("decision", ["reject", "snooze"])
async def test_reject_and_snooze_persist_without_creating_a_company(
    migrated_db: None, decision: str
) -> None:
    sub, email = _sub()
    user_id = await _seed_user_with_approvals(sub, email, [_LIGHTHOUSE])
    headers = _auth_header(sub, email)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        approval_id = (await client.get("/api/v1/approvals", headers=headers)).json()[0]["id"]
        decide = await client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": decision},
            headers=headers,
        )
        assert decide.status_code == 200
        after = (await client.get("/api/v1/approvals", headers=headers)).json()
        assert after == []

    assert await _companies_for(user_id) == []


@requires_db
async def test_approve_is_idempotent_on_duplicate_domain(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both approves fire back-to-back for one user; the NET rate-limit gate (default 60s
    # cooldown) would 429 the second, so drop the cooldown — this test is about idempotency,
    # not throttling (which tests/test_ratelimit.py covers).
    monkeypatch.setattr(settings, "run_cooldown_s", 0)
    sub, email = _sub()
    user_id = await _seed_user_with_approvals(
        sub,
        email,
        [_LIGHTHOUSE, {**_LIGHTHOUSE, "found_query": "again"}],
    )
    headers = _auth_header(sub, email)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ids = [row["id"] for row in (await client.get("/api/v1/approvals", headers=headers)).json()]
        for approval_id in ids:
            resp = await client.post(
                f"/api/v1/approvals/{approval_id}/decision",
                json={"decision": "approve"},
                headers=headers,
            )
            assert resp.status_code == 200

    # unique(user_id, domain) → both approvals map to the single company.
    assert len(await _companies_for(user_id)) == 1


@requires_db
async def test_invalid_decision_is_rejected(migrated_db: None) -> None:
    sub, email = _sub()
    await _seed_user_with_approvals(sub, email, [_LIGHTHOUSE])
    headers = _auth_header(sub, email)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        approval_id = (await client.get("/api/v1/approvals", headers=headers)).json()[0]["id"]
        resp = await client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "maybe"},
            headers=headers,
        )
    assert resp.status_code == 422


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    sub_a, email_a = _sub()
    sub_b, email_b = _sub()
    await _seed_user_with_approvals(sub_a, email_a, [_LIGHTHOUSE])
    headers_a = _auth_header(sub_a, email_a)
    headers_b = _auth_header(sub_b, email_b)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        approval_id = (await client.get("/api/v1/approvals", headers=headers_a)).json()[0]["id"]

        # User B sees an empty queue...
        assert (await client.get("/api/v1/approvals", headers=headers_b)).json() == []

        # ...and cannot decide on user A's approval.
        resp = await client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "approve"},
            headers=headers_b,
        )
        assert resp.status_code == 404
