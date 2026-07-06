import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import CandidateProfile, Company, Posting, User
from specula_api.db.session import async_session
from specula_api.main import create_app

TODAY = date.today()


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _sub() -> str:
    return f"test-sub-{uuid.uuid4()}"


def _auth_header(sub: str) -> dict[str, str]:
    token = mint(sub=sub, email=f"{uuid.uuid4()}@example.com", name="Test User")
    return {"Authorization": f"Bearer {token}"}


async def _set_tenant(session: object, user_id: uuid.UUID) -> None:
    from sqlalchemy import text

    await session.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
    )


async def _seed(
    *,
    sub: str,
    skills: list[str] | None = None,
    postings: list[dict[str, object]],
) -> uuid.UUID:
    """Create a fresh user with a candidate profile and the given postings, committed
    so the API (separate session) can read them. Each posting dict may set
    required_skills, seniority, work_mode, extraction_confidence, posted_at, and an
    optional `company` name."""
    async with async_session() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=sub)
        session.add(user)
        await session.flush()
        await _set_tenant(session, user.id)

        if skills is not None:
            session.add(CandidateProfile(user_id=user.id, skills=skills))

        companies: dict[str, Company] = {}
        for spec in postings:
            name = spec.get("company")
            company_id = None
            if name:
                if name not in companies:
                    c = Company(user_id=user.id, name=str(name), domain=f"{name}.example")
                    session.add(c)
                    await session.flush()
                    companies[str(name)] = c
                company_id = companies[str(name)].id
            p = Posting(
                user_id=user.id,
                company_id=company_id,
                source="test",
                source_url=f"https://example.com/{uuid.uuid4()}",
                content_hash=str(uuid.uuid4()),
                required_skills=spec.get("required_skills", []),
                seniority=spec.get("seniority"),
                work_mode=spec.get("work_mode"),
                extraction_confidence=spec.get("extraction_confidence", 90),
                posted_at=spec.get("posted_at", TODAY),
            )
            session.add(p)
        await session.commit()
        return user.id


async def _get(path: str, sub: str) -> object:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=_auth_header(sub))


@requires_db
async def test_insights_excludes_low_confidence_postings(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        skills=["Python"],
        postings=[
            {"required_skills": ["Python", "PyTorch"], "extraction_confidence": 94},
            {"required_skills": ["Python", "LangGraph"], "extraction_confidence": 88},
            {"required_skills": ["ROS"], "extraction_confidence": 42},  # low-confidence
        ],
    )

    resp = await _get("/api/v1/insights?period=8w", sub)
    assert resp.status_code == 200  # type: ignore[attr-defined]
    body = resp.json()  # type: ignore[attr-defined]
    assert body["totalAnalysed"] == 2
    assert body["lowConfExcluded"] == 1
    # The excluded posting's only skill (ROS) must not surface in any aggregate.
    assert all(s["skill"] != "ROS" for s in body["skillDemand"])


@requires_db
async def test_flipping_threshold_includes_the_low_confidence_posting(
    migrated_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specula_api.services import insights as insights_svc

    sub = _sub()
    await _seed(
        sub=sub,
        skills=["Python"],
        postings=[
            {"required_skills": ["Python"], "extraction_confidence": 94},
            {"required_skills": ["ROS"], "extraction_confidence": 42},
        ],
    )

    monkeypatch.setattr(insights_svc, "LOW_CONFIDENCE_THRESHOLD", 40)
    resp = await _get("/api/v1/insights?period=8w", sub)
    body = resp.json()  # type: ignore[attr-defined]
    assert body["totalAnalysed"] == 2
    assert body["lowConfExcluded"] == 0
    assert any(s["skill"] == "ROS" for s in body["skillDemand"])


@requires_db
async def test_insights_aggregate_correctness(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        skills=["Python"],
        postings=[
            {
                "required_skills": ["Python", "PyTorch"],
                "seniority": "Senior",
                "work_mode": "Remote",
                "company": "Mistral",
            },
            {
                "required_skills": ["Python", "LangGraph"],
                "seniority": "Senior",
                "work_mode": "Hybrid",
                "company": "n8n",
            },
        ],
    )

    body = (await _get("/api/v1/insights?period=8w", sub)).json()  # type: ignore[attr-defined]

    demand = {s["skill"]: s for s in body["skillDemand"]}
    assert demand["Python"]["pct"] == 100
    assert demand["PyTorch"]["pct"] == 50
    # Python is on the candidate profile → not a gap; PyTorch is missing → gap.
    assert demand["Python"]["gap"] is False
    assert demand["PyTorch"]["gap"] is True

    assert body["seniorityMix"] == [{"k": "Senior", "v": 100}]

    modes = {m["k"]: m for m in body["modeMix"]}
    assert modes["Remote"]["v"] == 50
    assert modes["Hybrid"]["v"] == 50
    assert modes["Remote"]["color"] == "var(--accent)"

    companies = {c["name"]: c["n"] for c in body["activeCompanies"]}
    assert companies == {"Mistral": 1, "n8n": 1}

    assert body["trend"]["weeks"] == ["w1", "w2", "w3", "w4", "w5", "w6", "w7", "w8"]


@requires_db
async def test_insights_period_windows_the_pool(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        skills=[],
        postings=[
            {"required_skills": ["Python"], "posted_at": TODAY - timedelta(days=3)},
            {"required_skills": ["Go"], "posted_at": TODAY - timedelta(days=40)},  # in 8w, not 4w
        ],
    )

    four = (await _get("/api/v1/insights?period=4w", sub)).json()  # type: ignore[attr-defined]
    eight = (await _get("/api/v1/insights?period=8w", sub)).json()  # type: ignore[attr-defined]
    assert four["totalAnalysed"] == 1
    assert eight["totalAnalysed"] == 2
    assert four["trend"]["weeks"] == ["w1", "w2", "w3", "w4"]


@requires_db
async def test_skills_gap_derives_missing_skills(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        skills=["Python", "PyTorch"],
        postings=[
            {"required_skills": ["Python", "PyTorch", "Kubernetes"]},
            {"required_skills": ["Python", "Kubernetes", "Go"]},
            {"required_skills": ["ROS"], "extraction_confidence": 42},  # low-conf, excluded
        ],
    )

    gap = (await _get("/api/v1/skills-gap", sub)).json()  # type: ignore[attr-defined]
    by_skill = {g["skill"]: g for g in gap}
    # Python/PyTorch are on the profile → not gaps. ROS is low-confidence → excluded.
    assert set(by_skill) == {"Kubernetes", "Go"}
    assert by_skill["Kubernetes"]["roles"] == 2
    assert by_skill["Go"]["roles"] == 1
    # Sorted most-demanded first.
    assert gap[0]["skill"] == "Kubernetes"


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    owner = _sub()
    await _seed(
        sub=owner,
        skills=["Python"],
        postings=[{"required_skills": ["Python", "PyTorch"], "company": "Mistral"}],
    )

    other = _sub()
    body = (await _get("/api/v1/insights?period=8w", other)).json()  # type: ignore[attr-defined]
    assert body["totalAnalysed"] == 0
    assert body["skillDemand"] == []
    assert body["activeCompanies"] == []

    gap = (await _get("/api/v1/skills-gap", other)).json()  # type: ignore[attr-defined]
    assert gap == []
