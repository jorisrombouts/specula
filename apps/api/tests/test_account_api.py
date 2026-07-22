import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import (
    Approval,
    CandidateProfile,
    Company,
    Lens,
    LlmCost,
    Posting,
    PostingState,
    Run,
    Score,
    SkillsTaxonomy,
    Targeting,
    User,
    UserSettings,
)
from specula_api.db.session import async_session, tenant_session
from specula_api.main import create_app

# Every per-user table (RLS-scoped, user_id FK ON DELETE CASCADE) that account deletion must
# drop. `users` (the identity row itself) and `skills_taxonomy` (global/unscoped) are NOT here.
_PER_USER_TABLES = [
    Company,
    Posting,
    Score,
    PostingState,
    Lens,
    Run,
    LlmCost,
    Approval,
    Targeting,
    CandidateProfile,
    UserSettings,
]


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


async def _make_user() -> User:
    """A committed user (not the rollback fixture) so the FK-backed RLS policies see it
    off-request. The `test-sub-` google_sub lets conftest's sweeper reap it."""
    async with async_session() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=f"test-sub-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        return user


def _auth_header(user: User) -> dict[str, str]:
    token = mint(sub=user.google_sub, email=user.email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


async def _seed_user_data(user_id: uuid.UUID, *, domain: str) -> dict[str, uuid.UUID]:
    """Populate one row in every per-user table for `user_id`."""
    async with tenant_session(user_id) as session:
        company = Company(user_id=user_id, name="Acme", domain=domain)
        session.add(company)
        await session.flush()

        posting = Posting(
            user_id=user_id,
            company_id=company.id,
            source="greenhouse",
            source_url="https://acme.example/jobs/1",
            content_hash=str(uuid.uuid4()),
            title="Staff Engineer",
            extraction_confidence=90,
        )
        session.add(posting)
        await session.flush()

        session.add_all(
            [
                Score(
                    posting_id=posting.id,
                    user_id=user_id,
                    factor_role=80,
                    factor_skill=70,
                    overlap_matched=3,
                    overlap_total=5,
                    rationale="Strong overlap",
                    scored_with="v1",
                ),
                PostingState(posting_id=posting.id, user_id=user_id, status="Saved"),
                Lens(user_id=user_id, name="All roles"),
                Run(user_id=user_id, kind="on_demand"),
                LlmCost(
                    user_id=user_id,
                    stage="extract",
                    model="gpt-4o-mini",
                    prompt_tokens=10,
                    completion_tokens=5,
                    cost_usd=Decimal("0.001500"),
                ),
                Approval(user_id=user_id, name="Candidate Co"),
                Targeting(user_id=user_id, role_titles=["ML Eng"]),
                CandidateProfile(user_id=user_id, headline="Engineer"),
                UserSettings(user_id=user_id, tweaks={"density": "compact"}),
            ]
        )
        return {"company_id": company.id, "posting_id": posting.id}


async def _count(user_id: uuid.UUID, model: type) -> int:
    async with tenant_session(user_id) as session:
        total = await session.scalar(select(func.count()).select_from(model))
        return int(total or 0)


async def _cleanup_users(*user_ids: uuid.UUID) -> None:
    async with async_session() as session:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


# --------------------------------------------------------------------------- export


@requires_db
async def test_export_contains_callers_rows_in_camelcase(migrated_db: None) -> None:
    user = await _make_user()
    try:
        await _seed_user_data(user.id, domain="acme-export.example")

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/account/export", headers=_auth_header(user))

        assert response.status_code == 200
        body = response.json()

        # Frozen ExportBundle shape — exactly these keys, all camelCase.
        assert set(body) == {
            "exportedAt",
            "candidate",
            "targeting",
            "companies",
            "postings",
            "scores",
            "lenses",
            "runs",
            "llmCosts",
        }
        assert body["companies"][0]["name"] == "Acme"
        assert body["candidate"]["headline"] == "Engineer"
        assert body["targeting"]["roleTitles"] == ["ML Eng"]
        assert len(body["postings"]) == 1
        assert len(body["scores"]) == 1

        # llmCosts must serialise to the frozen LlmCost interface (camelCase, cost as number).
        cost = body["llmCosts"][0]
        assert set(cost) == {
            "id",
            "runId",
            "companyId",
            "stage",
            "model",
            "promptTokens",
            "completionTokens",
            "embedTokens",
            "costUsd",
            "createdAt",
        }
        assert cost["stage"] == "extract"
        assert cost["promptTokens"] == 10
        assert cost["costUsd"] == 0.0015
    finally:
        await _cleanup_users(user.id)


@requires_db
async def test_export_excludes_vectors_and_global_taxonomy(migrated_db: None) -> None:
    user = await _make_user()
    async with async_session() as session:
        session.add(SkillsTaxonomy(canonical=f"python-{uuid.uuid4()}"))
        await session.commit()
    try:
        await _seed_user_data(user.id, domain="acme-novec.example")

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/account/export", headers=_auth_header(user))

        body = response.json()
        # skills_taxonomy is global — never in a per-user export.
        assert "skillsTaxonomy" not in body
        # 1536-float embedding vectors are excluded from the dump.
        assert "titleVec" not in body["postings"][0]
        assert "skillsVec" not in body["postings"][0]
        assert "skillsVec" not in body["candidate"]
    finally:
        await _cleanup_users(user.id)


@requires_db
async def test_export_is_tenant_disjoint(migrated_db: None) -> None:
    user_a = await _make_user()
    user_b = await _make_user()
    try:
        await _seed_user_data(user_a.id, domain="acme-a.example")
        await _seed_user_data(user_b.id, domain="acme-b.example")

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/account/export", headers=_auth_header(user_b))

        body = response.json()
        domains = {c["domain"] for c in body["companies"]}
        assert domains == {"acme-b.example"}
        assert "acme-a.example" not in domains
    finally:
        await _cleanup_users(user_a.id, user_b.id)


@requires_db
async def test_export_empty_for_fresh_user(migrated_db: None) -> None:
    user = await _make_user()
    try:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/account/export", headers=_auth_header(user))

        assert response.status_code == 200
        body = response.json()
        assert body["candidate"] is None
        assert body["targeting"] is None
        assert body["companies"] == []
        assert body["llmCosts"] == []
    finally:
        await _cleanup_users(user.id)


# --------------------------------------------------------------------------- delete cascade


@requires_db
async def test_delete_account_cascades_and_leaves_other_tenant_intact(migrated_db: None) -> None:
    user_a = await _make_user()
    user_b = await _make_user()
    async with async_session() as session:
        taxonomy_canonical = f"rust-{uuid.uuid4()}"
        session.add(SkillsTaxonomy(canonical=taxonomy_canonical))
        await session.commit()
    try:
        await _seed_user_data(user_a.id, domain="acme-del-a.example")
        await _seed_user_data(user_b.id, domain="acme-del-b.example")

        # Sanity: A has data in every per-user table before deletion.
        for model in _PER_USER_TABLES:
            assert await _count(user_a.id, model) >= 1, model.__name__

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/account", headers=_auth_header(user_a))
        assert response.status_code == 204

        # A's identity row is gone, and B's survives...
        async with async_session() as session:
            assert await session.get(User, user_a.id) is None
            assert await session.get(User, user_b.id) is not None
        # ...A's per-user rows are all gone; B's are all intact.
        for model in _PER_USER_TABLES:
            assert await _count(user_a.id, model) == 0, model.__name__
            assert await _count(user_b.id, model) >= 1, model.__name__

        # The global taxonomy row survives account deletion.
        async with async_session() as session:
            surviving = await session.scalar(
                select(SkillsTaxonomy).where(SkillsTaxonomy.canonical == taxonomy_canonical)
            )
            assert surviving is not None
    finally:
        async with async_session() as session:
            await session.execute(
                delete(SkillsTaxonomy).where(SkillsTaxonomy.canonical == taxonomy_canonical)
            )
            await session.commit()
        await _cleanup_users(user_a.id, user_b.id)


@requires_db
async def test_delete_account_is_scoped_to_caller(migrated_db: None) -> None:
    """User B calling DELETE /account removes B — never A."""
    user_a = await _make_user()
    user_b = await _make_user()
    try:
        await _seed_user_data(user_a.id, domain="acme-scope-a.example")

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/account", headers=_auth_header(user_b))
        assert response.status_code == 204

        async with async_session() as session:
            assert await session.get(User, user_a.id) is not None
            assert await session.get(User, user_b.id) is None
        assert await _count(user_a.id, Company) >= 1
    finally:
        await _cleanup_users(user_a.id, user_b.id)
