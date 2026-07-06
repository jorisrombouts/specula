"""Idempotent demo seeder: `python -m specula_api.seed`.

Populates a single demo user with representative rows across every M2 vertical so
the app (and E2E/onboarding previews) has real data to render before the M3/M4
discovery+scoring pipeline exists. Safe to run repeatedly — it deletes the demo
user's rows and reinserts.

RLS mechanics: the app connects as the non-superuser `specula_app` role, which OWNS
the schema. It owner-bypasses the (enabled-but-not-forced) `users` table, so the
demo user is found/created without a tenant context. The 10 per-user tables are
FORCE-RLS'd, so before touching any of them we set `app.user_id` to the demo user's
id — every seeded row's `user_id` must match it (the policy checks both USING and
WITH CHECK). `skills_taxonomy` is global (no RLS).
"""

import asyncio
from datetime import UTC, date, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import (
    Approval,
    CandidateProfile,
    Company,
    Lens,
    Posting,
    PostingState,
    Run,
    Score,
    SkillsTaxonomy,
    Targeting,
    User,
    UserSettings,
)
from specula_api.db.session import async_session

DEMO_GOOGLE_SUB = "demo-user"
DEMO_EMAIL = "demo@specula.app"

# Per-user tables to clear on reseed, in FK-safe order (children before parents).
_TENANT_TABLES = [
    Score,
    PostingState,
    Posting,
    Company,
    Lens,
    Approval,
    Run,
    Targeting,
    CandidateProfile,
    UserSettings,
]


async def _get_or_create_demo_user(session: AsyncSession) -> User:
    user = await session.scalar(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
    if user is None:
        user = User(google_sub=DEMO_GOOGLE_SUB, email=DEMO_EMAIL, name="Demo User")
        session.add(user)
        await session.flush()
    return user


async def _set_tenant(session: AsyncSession, user_id: object) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
    )


async def seed(session: AsyncSession) -> None:
    user = await _get_or_create_demo_user(session)
    uid = user.id

    # All per-user reads/writes below require the tenant GUC (FORCE RLS).
    await _set_tenant(session, uid)

    # Idempotent reset: clear the demo user's rows (RLS scopes each delete to them).
    for model in _TENANT_TABLES:
        await session.execute(delete(model))

    session.add(
        CandidateProfile(
            user_id=uid,
            headline="Applied ML engineer — LLM systems",
            location="Amsterdam, NL",
            work_mode="Hybrid",
            years=6,
            education="MSc Computer Science",
            languages=["English", "Dutch"],
            skills=["Python", "PyTorch", "LLMs", "RAG", "vLLM", "LangGraph"],
            projects=[{"name": "Agentic RAG", "note": "Retrieval + tool-use pipeline"}],
            experience=[{"role": "ML Engineer", "org": "Scaleup", "period": "2021-now"}],
        )
    )
    session.add(
        Targeting(
            user_id=uid,
            role_titles=["Applied Scientist", "ML Engineer", "AI Engineer"],
            seniority=["Senior", "Mid-Senior"],
            must_haves=["applied-LLM", "remote-EU friendly"],
            avoid=["pure research", "on-site only"],
            preferences="Agentic LLM systems, retrieval, evaluation.",
        )
    )
    session.add(UserSettings(user_id=uid, tweaks={"mstyle": "bars", "layout": "rows"}))

    all_lens = Lens(
        user_id=uid,
        name="All",
        short="Everything",
        is_default=True,
        active=True,
        modes=[],
        seeds=[],
    )
    foreign_lens = Lens(
        user_id=uid,
        name="Foreign HQ",
        short="Non-local HQ",
        origin_rule="foreign_hq",
        active=True,
        modes=["Remote", "Hybrid"],
        seeds=["remote EU LLM roles"],
    )
    session.add_all([all_lens, foreign_lens])

    mistral = Company(
        user_id=uid,
        name="Mistral AI",
        domain="mistral.ai",
        logo_url="https://icons.duckduckgo.com/ip3/mistral.ai.ico",
        ats="lever",
        hq_country="FR",
        hq_confidence=95,
        comp_estimate="€€€",
        tracking=True,
        status="approved",
    )
    n8n = Company(
        user_id=uid,
        name="n8n",
        domain="n8n.io",
        logo_url="https://icons.duckduckgo.com/ip3/n8n.io.ico",
        ats="ashby",
        hq_country="DE",
        hq_confidence=90,
        comp_estimate="€€",
        tracking=True,
        status="approved",
    )
    session.add_all([mistral, n8n])
    await session.flush()  # assign company ids for posting FKs

    # A representative pool. The last one is deliberately low-confidence so the
    # "excluded from Insights" invariant is testable downstream.
    postings = [
        Posting(
            user_id=uid,
            company_id=mistral.id,
            source="scrape",
            source_url="https://jobs.mistral.ai/applied-scientist-llm-agents",
            content_hash="hash-mistral-1",
            title="Applied Scientist — LLM Agents",
            role_family="Applied Scientist",
            city="Paris",
            country="FR",
            hq_country="FR",
            work_mode="Hybrid",
            seniority="Senior",
            required_skills=["PyTorch", "vLLM", "Python", "LangGraph"],
            nice_to_have=["Kubernetes", "Ray"],
            summary="Build tool-using LLM agents.",
            responsibilities=["Agent planning", "Eval harnesses"],
            still_open=True,
            extraction_confidence=94,
            posted_at=date(2026, 7, 1),
        ),
        Posting(
            user_id=uid,
            company_id=n8n.id,
            source="scrape",
            source_url="https://n8n.io/careers/ml-engineer-agents",
            content_hash="hash-n8n-1",
            title="ML Engineer — Workflow Agents",
            role_family="ML Engineer",
            city="Berlin",
            country="DE",
            hq_country="DE",
            work_mode="Remote",
            seniority="Senior",
            required_skills=["Python", "PyTorch", "LangGraph", "vLLM"],
            summary="Agentic workflow automation.",
            still_open=True,
            extraction_confidence=88,
            posted_at=date(2026, 6, 28),
        ),
        Posting(
            user_id=uid,
            company_id=None,
            source="scrape",
            source_url="https://example.com/robotics-foundation-role",
            content_hash="hash-lowconf-1",
            title="Research Engineer — Robotics Foundation Models",
            role_family="Research Engineer",
            city=None,
            country="US",
            hq_country="US",
            work_mode="Remote",
            seniority="Senior",
            required_skills=["PyTorch", "ROS"],
            summary="HQ origin only 64% confident.",
            still_open=True,
            extraction_confidence=42,
            posted_at=date(2026, 6, 20),
        ),
    ]
    session.add_all(postings)
    await session.flush()  # assign posting ids for score/state FKs

    scored = "specula-scoring/v0-demo"
    session.add_all(
        [
            Score(
                posting_id=postings[0].id,
                user_id=uid,
                factor_role=96,
                factor_skill=89,
                overlap_matched=8,
                overlap_total=9,
                rationale="Strong applied-LLM overlap.",
                scored_with=scored,
            ),
            Score(
                posting_id=postings[1].id,
                user_id=uid,
                factor_role=90,
                factor_skill=87,
                overlap_matched=7,
                overlap_total=9,
                rationale="Agentic focus fits.",
                scored_with=scored,
            ),
        ]
    )
    session.add(PostingState(posting_id=postings[0].id, user_id=uid, status="Saved"))
    session.add(
        PostingState(posting_id=postings[1].id, user_id=uid, status="Applied", feedback="positive")
    )

    session.add(
        Approval(
            user_id=uid,
            name="Lighthouse",
            domain="lighthouse.app",
            logo_url="https://icons.duckduckgo.com/ip3/lighthouse.app.ico",
            ats="greenhouse",
            hq_country="NL",
            found_query="machine learning amsterdam scaleup",
            why="NL-local ML team.",
            open_roles=3,
            hq_confidence=90,
            decision=None,
        )
    )
    session.add(
        Run(
            user_id=uid,
            kind="scheduled",
            status="done",
            started_at=datetime(2026, 7, 5, 8, 0, tzinfo=UTC),
            finished_at=datetime(2026, 7, 5, 8, 3, tzinfo=UTC),
            stats={"found": 13, "new": 7, "closed": 1, "low_conf_excluded": 1, "errors": 0},
        )
    )

    # Global taxonomy (unscoped; specula_app owns the table).
    for canonical, aliases in [("python", ["py"]), ("pytorch", ["torch"])]:
        exists = await session.scalar(
            select(SkillsTaxonomy).where(SkillsTaxonomy.canonical == canonical)
        )
        if exists is None:
            session.add(SkillsTaxonomy(canonical=canonical, aliases=aliases))


async def main() -> None:
    async with async_session() as session:
        await seed(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
