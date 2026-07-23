import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _auth_header() -> dict[str, str]:
    sub = f"test-sub-{uuid.uuid4()}"
    email = f"{uuid.uuid4()}@example.com"
    token = mint(sub=sub, email=email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


@requires_db
async def test_get_targeting_for_fresh_user_returns_empty_defaults(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/targeting", headers=_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["roleTitles"] == []
    assert body["seniority"] == []
    assert body["mustHaves"] == []
    assert body["avoid"] == []
    assert body["preferences"] is None


@requires_db
async def test_put_targeting_persists_and_echoes_camelcase(migrated_db: None) -> None:
    headers = _auth_header()
    payload = {
        "roleTitles": ["ML Eng"],
        "seniority": ["Senior"],
        "mustHaves": ["Python"],
        "avoid": ["On-call"],
        "preferences": "Remote only",
    }

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/targeting", json=payload, headers=headers)
        assert put_response.status_code == 200
        put_body = put_response.json()
        for key, value in payload.items():
            assert put_body[key] == value

        get_response = await client.get("/api/v1/targeting", headers=headers)
        assert get_response.status_code == 200
        get_body = get_response.json()
        for key, value in payload.items():
            assert get_body[key] == value


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    user_a_headers = _auth_header()
    user_b_headers = _auth_header()
    payload = {
        "roleTitles": ["ML Eng"],
        "seniority": [],
        "mustHaves": [],
        "avoid": [],
        "preferences": None,
    }

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/targeting", json=payload, headers=user_a_headers)
        assert put_response.status_code == 200

        get_response = await client.get("/api/v1/targeting", headers=user_b_headers)
        assert get_response.status_code == 200
        body = get_response.json()
        assert body["roleTitles"] == []


@requires_db
async def test_put_targeting_twice_updates_existing_row(migrated_db: None) -> None:
    # The second PUT hits the UPDATE path; `updated_at`'s server-side onupdate must not
    # break the response serialization (regression: MissingGreenlet on the expired attr).
    headers = _auth_header()
    p1 = {
        "roleTitles": ["ML Engineer"],
        "seniority": ["Mid"],
        "mustHaves": [],
        "avoid": [],
        "preferences": "a",
    }
    p2 = {
        "roleTitles": ["ML Engineer", "AI Engineer"],
        "seniority": ["Senior"],
        "mustHaves": ["Python"],
        "avoid": [],
        "preferences": "b",
    }
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.put("/api/v1/targeting", json=p1, headers=headers)).status_code == 200
        r2 = await client.put("/api/v1/targeting", json=p2, headers=headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["preferences"] == "b"
        assert r2.json()["seniority"] == ["Senior"]
