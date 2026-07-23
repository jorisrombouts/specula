import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import CandidateProfile, User
from specula_api.db.session import async_session, tenant_session
from specula_api.main import create_app
from specula_api.schemas.candidate import CandidateOut


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


def test_candidate_out_tolerates_legacy_out_of_enum_values() -> None:
    # The READ model must never 500 on values written before these enums existed (or left
    # by a rollback). Strict Literals belong on writes (CandidateIn); reads are lenient.
    out = CandidateOut.model_validate(
        {
            "headline": None,
            "location": None,
            "work_mode": ["Remote, Hybrid, On-site"],  # not a valid Mode
            "visa": "EU visa",  # legacy free-text, not a Visa option
            "years": None,
            "education": [{"degree": "", "field": "AI", "institution": "", "year": None}],
            "languages": [{"language": "English", "level": ""}],  # "" not a CefrLevel
            "skills": [],
            "projects": [],
            "experience": [],
            "updated_at": datetime.now(UTC),
        }
    )
    assert out.visa == "EU visa"
    assert out.work_mode == ["Remote, Hybrid, On-site"]
    assert out.languages[0].level == ""


@requires_db
async def test_get_candidate_tolerates_legacy_row(migrated_db: None) -> None:
    # A profile saved by the pre-enum UI must stay READABLE: GET must surface it, not 500.
    sub = f"test-sub-{uuid.uuid4()}"
    token = mint(sub=sub, email=f"{uuid.uuid4()}@example.com", name="Legacy User")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as s:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=sub)
        s.add(user)
        await s.commit()
        uid = user.id

    async with tenant_session(uid) as s:
        s.add(
            CandidateProfile(
                user_id=uid,
                work_mode=["Remote, Hybrid, On-site"],  # corrupted single element
                visa="EU visa",  # legacy free-text, not a Visa option
                languages=[{"language": "English", "level": ""}],  # "" not a CefrLevel
                education=[],
                experience=[],
            )
        )

    try:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/candidate", headers=headers)
        assert resp.status_code == 200  # must NOT 500 on legacy / out-of-enum data
        body = resp.json()
        assert body["visa"] == "EU visa"
        assert body["workMode"] == ["Remote, Hybrid, On-site"]
        assert body["languages"][0]["level"] == ""
    finally:
        async with async_session() as s:
            await s.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
            await s.commit()
