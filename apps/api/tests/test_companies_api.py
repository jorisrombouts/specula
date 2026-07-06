import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import Company, User
from specula_api.db.session import async_session
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


async def _seed_user_with_companies(*companies: dict[str, Any]) -> dict[str, str]:
    """Create a fresh user + their companies directly, return the auth header."""
    sub = f"test-sub-{uuid.uuid4()}"
    email = f"{uuid.uuid4()}@example.com"
    async with async_session() as session:
        user = User(google_sub=sub, email=email, name="Test User")
        session.add(user)
        await session.flush()
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user.id))
        )
        for data in companies:
            session.add(Company(user_id=user.id, **data))
        await session.commit()

    token = mint(sub=sub, email=email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


@requires_db
async def test_get_lists_the_users_companies(migrated_db: None) -> None:
    headers = await _seed_user_with_companies(
        {
            "name": "Mistral AI",
            "domain": "mistral.ai",
            "logo_url": "https://icons.duckduckgo.com/ip3/mistral.ai.ico",
            "ats": "lever",
            "hq_country": "FR",
            "hq_confidence": 95,
            "comp_estimate": "€€€",
            "tracking": True,
        },
        {
            "name": "n8n",
            "domain": "n8n.io",
            "ats": "ashby",
            "hq_country": "DE",
            "hq_confidence": 90,
            "comp_estimate": "€€",
            "tracking": False,
        },
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/companies", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    by_name = {c["name"]: c for c in body}
    mistral = by_name["Mistral AI"]
    # camelCase + short TS keys mapped from DB columns
    assert mistral["domain"] == "mistral.ai"
    assert mistral["ats"] == "lever"
    assert mistral["hq"] == "FR"
    assert mistral["conf"] == 95
    assert mistral["comp"] == "€€€"
    assert mistral["logo"] == "https://icons.duckduckgo.com/ip3/mistral.ai.ico"
    assert mistral["tracking"] is True
    assert mistral["flag"] == "🇫🇷"  # derived from the ISO country code
    assert mistral["open"] == 0  # no postings wired → derived count is 0
    assert "id" in mistral
    assert by_name["n8n"]["tracking"] is False


@requires_db
async def test_patch_tracking_toggle_persists(migrated_db: None) -> None:
    headers = await _seed_user_with_companies(
        {"name": "Mistral AI", "domain": "mistral.ai", "tracking": True},
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = (await client.get("/api/v1/companies", headers=headers)).json()
        company_id = listed[0]["id"]

        patch = await client.patch(
            f"/api/v1/companies/{company_id}",
            json={"tracking": False},
            headers=headers,
        )
        assert patch.status_code == 200
        assert patch.json()["tracking"] is False

        again = (await client.get("/api/v1/companies", headers=headers)).json()
        assert again[0]["tracking"] is False


@requires_db
async def test_patch_updates_other_editable_fields(migrated_db: None) -> None:
    headers = await _seed_user_with_companies(
        {"name": "Mistral AI", "domain": "mistral.ai", "ats": "lever"},
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_id = (await client.get("/api/v1/companies", headers=headers)).json()[0]["id"]
        patch = await client.patch(
            f"/api/v1/companies/{company_id}",
            json={"name": "Mistral", "ats": "greenhouse", "compEstimate": "€€€€"},
            headers=headers,
        )
        assert patch.status_code == 200
        body = patch.json()
        assert body["name"] == "Mistral"
        assert body["ats"] == "greenhouse"
        assert body["comp"] == "€€€€"


@requires_db
async def test_patch_conflicting_domain_returns_409(migrated_db: None) -> None:
    headers = await _seed_user_with_companies(
        {"name": "A", "domain": "a.com"},
        {"name": "B", "domain": "b.com"},
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = (await client.get("/api/v1/companies", headers=headers)).json()
        b_id = next(c["id"] for c in listed if c["name"] == "B")
        patch = await client.patch(
            f"/api/v1/companies/{b_id}",
            json={"domain": "a.com"},
            headers=headers,
        )
        assert patch.status_code == 409


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    owner_headers = await _seed_user_with_companies(
        {"name": "Mistral AI", "domain": "mistral.ai", "tracking": True},
    )
    other_headers = await _seed_user_with_companies(
        {"name": "Other Co", "domain": "other.com"},
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_id = (await client.get("/api/v1/companies", headers=owner_headers)).json()[0]["id"]

        other_list = (await client.get("/api/v1/companies", headers=other_headers)).json()
        assert [c["name"] for c in other_list] == ["Other Co"]

        # The other tenant cannot patch the owner's company → 404 (invisible under RLS).
        patch = await client.patch(
            f"/api/v1/companies/{owner_id}",
            json={"tracking": False},
            headers=other_headers,
        )
        assert patch.status_code == 404
