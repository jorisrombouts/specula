"""Live smoke test: the manual "prove the product" gate, and the source of committed
recorded fixtures (tests/fixtures/pipeline) — when the pipeline's shape changes, re-run this
against real OpenAI/ATS traffic and use its output to refresh those fixtures.

Skipped unless explicitly opted in (`RUN_LIVE_SMOKE=1`) with a real `OPENAI_API_KEY`, and
never collected as part of the normal suite (pyproject's `addopts = -m "not live"` excludes
the `live` marker by default; CI runs the default). Run it with:

    RUN_LIVE_SMOKE=1 OPENAI_API_KEY=sk-... uv run pytest -m live
"""

import os

import pytest
from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import settings
from specula_api.db.models import Approval, CandidateProfile, Lens, Posting, Score, Targeting
from specula_api.pipeline.deps import build_live_deps
from specula_api.services.approval import apply_decision
from specula_api.services.run import create_run, ingest_company, run_discovery

_RUN_LIVE = os.getenv("RUN_LIVE_SMOKE") == "1"
_HAS_KEY = bool(settings.openai_api_key)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_RUN_LIVE and _HAS_KEY),
        reason="live smoke: set RUN_LIVE_SMOKE=1 and OPENAI_API_KEY to run",
    ),
]


async def _seed_realistic_pool(session: AsyncSession, user_id: object) -> None:
    session.add(
        Targeting(
            user_id=user_id,
            role_titles=["Machine Learning Engineer", "AI Engineer"],
            seniority=["Mid", "Senior"],
            must_haves=["Python"],
            preferences="Applied ML / LLM engineering, remote-EU friendly.",
        )
    )
    session.add(
        CandidateProfile(
            user_id=user_id,
            headline="ML Engineer",
            location="Amsterdam, NL",
            work_mode="Remote-first (EU)",
            years=5,
            skills=["Python", "PyTorch", "RAG", "AWS", "Docker"],
        )
    )
    session.add(
        Lens(
            user_id=user_id,
            name="Remote EU",
            seeds=["machine learning engineer remote europe"],
            scope="Remote EU",
            modes=["Remote"],
            active=True,
        )
    )
    await session.flush()


@requires_db
async def test_live_smoke_discovers_ingests_and_scores_a_real_posting(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    await _seed_realistic_pool(db_session, user.id)

    deps = build_live_deps(settings)
    try:
        run = await create_run(db_session, user.id)
        await run_discovery(db_session, user.id, run.id, deps)
        assert run.status == "done"

        approvals = (
            await db_session.scalars(select(Approval).where(Approval.user_id == user.id))
        ).all()
        assert len(approvals) >= 1

        result = await apply_decision(db_session, user.id, approvals[0].id, "approve")
        assert result is not None
        _approval, company_id = result
        assert company_id is not None

        await ingest_company(db_session, user.id, company_id, deps)
    finally:
        await deps.aclose()

    postings = (
        await db_session.scalars(
            select(Posting).where(Posting.user_id == user.id, Posting.company_id == company_id)
        )
    ).all()
    real_postings = [p for p in postings if p.title]
    assert len(real_postings) >= 1

    scored = [p for p in real_postings if await db_session.get(Score, p.id) is not None]
    assert scored, "expected at least one extracted posting to have a Score row"
    score = await db_session.get(Score, scored[0].id)
    assert score is not None
    assert score.rationale != ""
