import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import Lens, Posting, User
from specula_api.db.session import async_session
from specula_api.main import create_app
from specula_api.services.lens_filter import lens_where, new_predicate

DEMO_GOOGLE_SUB = "demo-user"


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _auth_header(sub: str | None = None) -> dict[str, str]:
    sub = sub or f"test-sub-{uuid.uuid4()}"
    email = f"{uuid.uuid4()}@example.com"
    token = mint(sub=sub, email=email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


async def _demo_user_id() -> uuid.UUID:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
        assert user is not None, "demo user must be seeded (python -m specula_api.seed)"
        return user.id


@requires_db
async def test_get_lenses_lazy_creates_default(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/lenses", headers=_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    lens = body[0]
    assert lens["name"] == "All"
    # A fresh user has no postings → derived counts are zero, never absent.
    assert lens["count"] == 0
    assert lens["isNew"] == 0
    # Contract fields (camelCase), nullable columns coerced to "".
    assert lens["modes"] == []
    assert lens["origin"] == ""
    assert lens["active"] is True


@requires_db
async def test_create_patch_delete_lens_happy_path(migrated_db: None) -> None:
    headers = _auth_header()
    payload = {
        "name": "Remote EU",
        "short": "Remote",
        "scope": "EU",
        "modes": ["Remote"],
        "origin": "",
        "focus": "async-first",
        "seeds": ["remote ML EU"],
        "active": True,
    }

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post("/api/v1/lenses", json=payload, headers=headers)
        assert create.status_code == 201
        created = create.json()
        for key, value in payload.items():
            assert created[key] == value
        assert created["count"] == 0
        assert created["isNew"] == 0
        lens_id = created["id"]

        listed = await client.get("/api/v1/lenses", headers=headers)
        names = {lens["name"] for lens in listed.json()}
        assert names == {"All", "Remote EU"}

        deactivate = await client.patch(
            f"/api/v1/lenses/{lens_id}", json={"active": False}, headers=headers
        )
        assert deactivate.status_code == 200
        assert deactivate.json()["active"] is False

        rename = await client.patch(
            f"/api/v1/lenses/{lens_id}", json={"name": "Renamed"}, headers=headers
        )
        assert rename.status_code == 200
        renamed = rename.json()
        assert renamed["name"] == "Renamed"
        assert renamed["active"] is False  # partial update leaves other fields intact

        delete = await client.delete(f"/api/v1/lenses/{lens_id}", headers=headers)
        assert delete.status_code == 204

        after = await client.get("/api/v1/lenses", headers=headers)
        assert {lens["name"] for lens in after.json()} == {"All"}


@requires_db
async def test_counts_are_derived_not_stored(migrated_db: None) -> None:
    demo_id = await _demo_user_id()
    headers = _auth_header(sub=DEMO_GOOGLE_SUB)
    payload = {"name": "Counts Probe", "modes": ["Remote"], "origin": "", "scope": ""}

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post("/api/v1/lenses", json=payload, headers=headers)
        assert create.status_code == 201
        created = create.json()
        lens_id = created["id"]
        try:
            # Independently compute what the filter SHOULD yield over the seeded pool.
            probe = Lens(modes=["Remote"], origin_rule=None, scope=None, is_default=False)
            preds = lens_where(probe)
            async with async_session() as session:
                # postings is FORCE-RLS — the direct query needs the tenant GUC too.
                await session.execute(
                    text("SELECT set_config('app.user_id', :uid, true)").bindparams(
                        uid=str(demo_id)
                    )
                )
                expected_count = await session.scalar(
                    select(func.count())
                    .select_from(Posting)
                    .where(Posting.user_id == demo_id, *preds)
                )
                expected_new = await session.scalar(
                    select(func.count())
                    .select_from(Posting)
                    .where(Posting.user_id == demo_id, *preds, new_predicate())
                )

            assert expected_count is not None
            assert expected_count > 0  # meaningful, non-empty assertion over the seed
            assert created["count"] == expected_count
            assert created["isNew"] == expected_new
        finally:
            await client.delete(f"/api/v1/lenses/{lens_id}", headers=headers)


@requires_db
async def test_cannot_delete_default_lens(migrated_db: None) -> None:
    headers = _auth_header(sub=DEMO_GOOGLE_SUB)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get("/api/v1/lenses", headers=headers)
        default = next(lens for lens in listed.json() if lens["name"] == "All")

        delete = await client.delete(f"/api/v1/lenses/{default['id']}", headers=headers)
        assert delete.status_code == 409

        after = await client.get("/api/v1/lenses", headers=headers)
        assert any(lens["name"] == "All" for lens in after.json())


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    user_a = _auth_header()
    user_b = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post("/api/v1/lenses", json={"name": "Alpha Only"}, headers=user_a)
        assert create.status_code == 201

        listed_b = await client.get("/api/v1/lenses", headers=user_b)
        assert listed_b.status_code == 200
        names_b = {lens["name"] for lens in listed_b.json()}
        assert names_b == {"All"}  # B sees only its own lazily-created default


@requires_db
async def test_summary_exposes_is_default(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rows = (await client.get("/api/v1/lenses", headers=_auth_header())).json()
    assert any(r["isDefault"] for r in rows)
    assert all("isDefault" in r for r in rows)
