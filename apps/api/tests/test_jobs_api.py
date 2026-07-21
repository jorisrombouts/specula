import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import Company, Lens, Posting, Score, User
from specula_api.db.session import async_session
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _sub_email() -> tuple[str, str]:
    return f"test-sub-{uuid.uuid4()}", f"{uuid.uuid4()}@example.com"


def _auth_header(sub: str, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint(sub=sub, email=email, name='Test User')}"}


async def _seed_pool(sub: str, email: str) -> dict[str, uuid.UUID]:
    """Insert a user + a controlled 4-posting pool + two lenses, directly through the
    DB (there is no create-posting endpoint). Mirrors seed.py's RLS handling: set the
    tenant GUC before touching the FORCE-RLS per-user tables."""
    today = date.today()
    async with async_session() as session:
        user = User(google_sub=sub, email=email, name="Test User")
        session.add(user)
        await session.flush()
        uid = user.id
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(uid))
        )

        c_high = Company(user_id=uid, name="Mistral AI", domain="mistral.ai", hq_confidence=95)
        c_low = Company(user_id=uid, name="Sereact", domain="sereact.ai", hq_confidence=64)
        session.add_all([c_high, c_low])
        await session.flush()

        all_lens = Lens(user_id=uid, name="All", short="Everything", is_default=True, modes=[])
        foreign_lens = Lens(
            user_id=uid,
            name="Foreign HQ",
            short="Non-local HQ",
            is_default=False,
            origin_rule="foreign_hq",
            modes=["Remote", "Hybrid"],
        )
        session.add_all([all_lens, foreign_lens])

        # (label, company, mode, country, hq, role, skill, deadline_off, posted_off)
        specs = [
            ("pA", c_high, "Remote", "FR", "FR", 96, 89, 20, 3),  # local, new
            ("pB", c_low, "Remote", "NL", "GB", 84, 88, 3, 3),  # foreign, new
            ("pC", c_high, "Hybrid", "ES", "FR", 90, 86, 10, 30),  # foreign, old
            ("pD", c_high, "On-site", "DE", "US", 78, 40, 2, 30),  # low-skill red flag, old
        ]
        ids: dict[str, uuid.UUID] = {}
        for label, company, mode, country, hq, role, skill, dl, posted in specs:
            posting = Posting(
                user_id=uid,
                company_id=company.id,
                source="scrape",
                source_url=f"https://example.com/{label}",
                content_hash=f"hash-{label}-{uid}",
                title=f"Role {label}",
                work_mode=mode,
                country=country,
                hq_country=hq,
                seniority="Senior",
                required_skills=["Python", "PyTorch"],
                summary=f"summary {label}",
                responsibilities=[f"do {label}"],
                extraction_confidence=90,
                deadline_at=today + timedelta(days=dl),
                posted_at=today - timedelta(days=posted),
            )
            session.add(posting)
            await session.flush()
            ids[label] = posting.id
            session.add(
                Score(
                    posting_id=posting.id,
                    user_id=uid,
                    factor_role=role,
                    factor_skill=skill,
                    overlap_matched=7,
                    overlap_total=9,
                    rationale=f"rationale {label}",
                    scored_with="test/v0",
                )
            )

        ids["user"] = uid
        ids["all_lens"] = all_lens.id
        ids["foreign_lens"] = foreign_lens.id
        await session.commit()
    return ids


@requires_db
async def test_get_jobs_default_lens_returns_scored_pool_sorted_by_match(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['all_lens']}&sort=match", headers=_auth_header(sub, email)
        )
    assert resp.status_code == 200
    body = resp.json()
    matches = [j["match"] for j in body["jobs"]]
    assert len(matches) == 4
    assert matches == sorted(matches, reverse=True)
    assert body["jobs"][0]["id"] == str(ids["pA"])  # highest match
    assert body["sort"] == "match"


@requires_db
async def test_lens_summaries_have_derived_counts(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['all_lens']}&sort=match", headers=_auth_header(sub, email)
        )
    body = resp.json()
    summaries = {lens["name"]: lens for lens in body["lenses"]}
    assert summaries["All"]["count"] == 4  # DERIVED, not stored
    assert summaries["All"]["isNew"] == 2  # pA + pB posted within 7 days
    assert summaries["Foreign HQ"]["count"] == 2  # pB + pC (foreign_hq ∩ Remote/Hybrid)


@requires_db
async def test_foreign_hq_lens_filters_by_origin_and_modes(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['foreign_lens']}&sort=match", headers=_auth_header(sub, email)
        )
    body = resp.json()
    returned = {j["id"] for j in body["jobs"]}
    assert returned == {str(ids["pB"]), str(ids["pC"])}
    # pA excluded (local HQ), pD excluded (On-site not in lens modes)
    assert str(ids["pA"]) not in returned
    assert str(ids["pD"]) not in returned


@requires_db
async def test_sort_by_deadline_orders_ascending(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['all_lens']}&sort=deadline", headers=_auth_header(sub, email)
        )
    body = resp.json()
    days = [j["deadlineDays"] for j in body["jobs"]]
    assert days == sorted(days)
    assert body["jobs"][0]["id"] == str(ids["pD"])  # closes soonest


@requires_db
async def test_sort_by_new_puts_new_postings_first(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['all_lens']}&sort=new", headers=_auth_header(sub, email)
        )
    body = resp.json()
    first_two = {j["id"] for j in body["jobs"][:2]}
    assert first_two == {str(ids["pA"]), str(ids["pB"])}


@requires_db
async def test_low_skill_posting_gets_red_flag(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['all_lens']}&sort=match", headers=_auth_header(sub, email)
        )
    body = resp.json()
    pd = next(j for j in body["jobs"] if j["id"] == str(ids["pD"]))
    assert pd["redFlag"] == "Low required-skill overlap"
    assert pd["match"] <= 72


@requires_db
async def test_get_single_job_returns_full_record(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/jobs/{ids['pA']}", headers=_auth_header(sub, email))
    assert resp.status_code == 200
    job = resp.json()
    assert job["id"] == str(ids["pA"])
    assert job["title"] == "Role pA"
    assert job["company"] == "Mistral AI"
    assert job["summary"] == "summary pA"
    assert job["rationale"] == "rationale pA"
    assert job["factors"]["role"] == 96
    assert job["overlap"] == [7, 9]
    assert job["stack"] == ["Python", "PyTorch"]
    assert job["responsibilities"] == ["do pA"]


@requires_db
async def test_get_missing_job_returns_404(migrated_db: None) -> None:
    sub, email = _sub_email()
    await _seed_pool(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/jobs/{uuid.uuid4()}", headers=_auth_header(sub, email))
    assert resp.status_code == 404


@requires_db
async def test_patch_state_persists_and_round_trips(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    headers = _auth_header(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        patch = {"status": "Saved", "note": "referred by Anna", "feedback": "positive"}
        resp = await client.patch(f"/api/v1/jobs/{ids['pB']}/state", json=patch, headers=headers)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["status"] == "Saved"
        assert updated["note"] == "referred by Anna"
        assert updated["feedback"] == "positive"

        job = (await client.get(f"/api/v1/jobs/{ids['pB']}", headers=headers)).json()
        assert job["status"] == "Saved"

        listed = (
            await client.get(f"/api/v1/jobs?lens={ids['all_lens']}&sort=match", headers=headers)
        ).json()
        pb = next(j for j in listed["jobs"] if j["id"] == str(ids["pB"]))
        assert pb["status"] == "Saved"


@requires_db
async def test_patch_state_partial_update_keeps_other_fields(migrated_db: None) -> None:
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)
    headers = _auth_header(sub, email)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.patch(
            f"/api/v1/jobs/{ids['pB']}/state", json={"status": "Saved"}, headers=headers
        )
        resp = await client.patch(
            f"/api/v1/jobs/{ids['pB']}/state", json={"note": "call Tue"}, headers=headers
        )
        updated = resp.json()
        assert updated["status"] == "Saved"  # preserved from first PATCH
        assert updated["note"] == "call Tue"


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    sub_a, email_a = _sub_email()
    ids = await _seed_pool(sub_a, email_a)
    sub_b, email_b = _sub_email()
    headers_b = _auth_header(sub_b, email_b)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # user B has no lens; querying A's lens id sees nothing of A's
        resp = await client.get(f"/api/v1/jobs/{ids['pA']}", headers=headers_b)
        assert resp.status_code == 404

        patch = await client.patch(
            f"/api/v1/jobs/{ids['pA']}/state", json={"status": "Saved"}, headers=headers_b
        )
        assert patch.status_code == 404

        # and A's row is untouched
        headers_a = _auth_header(sub_a, email_a)
        job_a = (await client.get(f"/api/v1/jobs/{ids['pA']}", headers=headers_a)).json()
        assert job_a["status"] is None


@requires_db
async def test_dedup_group_collapses_the_pool_and_its_derived_counts(migrated_db: None) -> None:
    """Spec §5: "the pool is deduped on read."

    pA and pC become one role reaching us twice. The list must show 3, and — because counts
    are DERIVED from the same pool — the lens badge must read 3 too, not 4. A badge saying 4
    over a list of 3 is exactly the inconsistency the derived-counts invariant exists to stop.
    """
    sub, email = _sub_email()
    ids = await _seed_pool(sub, email)

    group = uuid.uuid4()
    async with async_session() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(ids["user"]))
        )
        await session.execute(
            text("UPDATE postings SET dedup_group = :g WHERE id = ANY(:ids)").bindparams(
                g=group, ids=[ids["pA"], ids["pC"]]
            )
        )
        await session.commit()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/jobs?lens={ids['all_lens']}&sort=match", headers=_auth_header(sub, email)
        )

    body = resp.json()
    returned = [j["id"] for j in body["jobs"]]
    assert len(returned) == 3
    # pA and pC share confidence, so the representative is whichever the ranking picks — but
    # exactly one of them may appear.
    assert len({str(ids["pA"]), str(ids["pC"])} & set(returned)) == 1
    assert str(ids["pB"]) in returned
    assert str(ids["pD"]) in returned

    summaries = {lens["name"]: lens for lens in body["lenses"]}
    assert summaries["All"]["count"] == 3  # derived over groups, not rows
