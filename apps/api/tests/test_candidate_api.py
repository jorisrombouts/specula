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
async def test_get_candidate_for_fresh_user_returns_empty_defaults(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/candidate", headers=_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["headline"] is None
    assert body["location"] is None
    assert body["workMode"] is None
    assert body["visa"] is None
    assert body["years"] is None
    assert body["education"] is None
    assert body["languages"] == []
    assert body["skills"] == []
    assert body["projects"] == []
    assert body["experience"] == []


@requires_db
async def test_put_candidate_persists_and_echoes_camelcase(migrated_db: None) -> None:
    headers = _auth_header()
    payload = {
        "headline": "ML Engineer",
        "location": "Berlin",
        "workMode": "Remote",
        "visa": "EU citizen",
        "years": 7,
        "education": "MSc Computer Science",
        "languages": ["English", "German"],
        "skills": ["Python", "PyTorch"],
        "projects": [{"name": "Specula", "note": "role ledger"}],
        "experience": [{"role": "ML Eng", "org": "Acme", "period": "2021-2024"}],
    }

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/candidate", json=payload, headers=headers)
        assert put_response.status_code == 200
        put_body = put_response.json()
        for key, value in payload.items():
            assert put_body[key] == value

        get_response = await client.get("/api/v1/candidate", headers=headers)
        assert get_response.status_code == 200
        get_body = get_response.json()
        for key, value in payload.items():
            assert get_body[key] == value


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    user_a_headers = _auth_header()
    user_b_headers = _auth_header()
    payload = {
        "headline": "ML Engineer",
        "location": "Berlin",
        "workMode": "Remote",
        "visa": None,
        "years": 7,
        "education": None,
        "languages": [],
        "skills": ["Python"],
        "projects": [],
        "experience": [],
    }

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/candidate", json=payload, headers=user_a_headers)
        assert put_response.status_code == 200

        get_response = await client.get("/api/v1/candidate", headers=user_b_headers)
        assert get_response.status_code == 200
        body = get_response.json()
        assert body["headline"] is None
        assert body["skills"] == []
