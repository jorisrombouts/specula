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
    assert body["workMode"] == []
    assert body["visa"] is None
    assert body["years"] is None
    assert body["education"] == []
    assert body["languages"] == []
    assert body["skills"] == []
    assert body["projects"] == []
    assert body["experience"] == []


_VALID_PAYLOAD = {
    "headline": "ML Engineer",
    "location": "Berlin",
    "workMode": ["Remote", "Hybrid"],
    "visa": "Require visa sponsorship",
    "years": 7,
    "education": [
        {"degree": "MSc", "field": "CS", "institution": "TU Berlin", "year": 2018},
    ],
    "languages": [{"language": "English", "level": "C2"}],
    "skills": ["Python", "PyTorch"],
    "projects": [{"name": "Specula", "note": "role ledger"}],
    "experience": [
        {"role": "ML Eng", "org": "Acme", "startYear": 2021, "endYear": None},
    ],
}


@requires_db
async def test_put_candidate_persists_structured_shapes(migrated_db: None) -> None:
    headers = _auth_header()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/candidate", json=_VALID_PAYLOAD, headers=headers)
        assert put_response.status_code == 200
        put_body = put_response.json()
        for key, value in _VALID_PAYLOAD.items():
            assert put_body[key] == value

        get_body = (await client.get("/api/v1/candidate", headers=headers)).json()
        for key, value in _VALID_PAYLOAD.items():
            assert get_body[key] == value


@requires_db
async def test_put_candidate_rejects_out_of_set_values(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    bad_bodies = [
        {**_VALID_PAYLOAD, "visa": "not a real option"},
        {**_VALID_PAYLOAD, "workMode": ["Telepathy"]},
        {**_VALID_PAYLOAD, "languages": [{"language": "English", "level": "Z9"}]},
        {
            **_VALID_PAYLOAD,
            "experience": [{"role": "r", "org": "o", "startYear": 1000, "endYear": 2020}],
        },
    ]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for body in bad_bodies:
            resp = await client.put("/api/v1/candidate", json=body, headers=_auth_header())
            assert resp.status_code == 422, body


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    user_a_headers = _auth_header()
    user_b_headers = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put(
            "/api/v1/candidate", json=_VALID_PAYLOAD, headers=user_a_headers
        )
        assert put_response.status_code == 200

        body = (await client.get("/api/v1/candidate", headers=user_b_headers)).json()
        assert body["headline"] is None
        assert body["skills"] == []
