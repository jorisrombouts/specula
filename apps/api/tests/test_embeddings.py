from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from conftest import make_user, set_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Posting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.embeddings import embed_posting
from specula_api.pipeline.http import FetchedDoc
from specula_api.pipeline.openai_client import RecordedOpenAIClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"


class _StubFetcher:
    """Never actually called — embed_posting doesn't fetch."""

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


def _deps() -> PipelineDeps:
    return PipelineDeps(
        openai=RecordedOpenAIClient(FIXTURES_DIR),
        fetcher=_StubFetcher(),
        settings=Settings(),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )


async def _make_posting(
    session: AsyncSession, user_id: object, *, title: str | None, skills: list[str]
) -> Posting:
    external_id = uuid4()
    posting = Posting(
        user_id=user_id,
        source="greenhouse",
        source_url=f"https://boards.greenhouse.io/acme/jobs/{external_id}",
        content_hash=f"hash-{external_id}",
        title=title,
        required_skills=skills,
    )
    session.add(posting)
    await session.flush()
    return posting


# --- embed_posting ----------------------------------------------------------------


@requires_db
async def test_embed_posting_sets_title_vec_and_skills_vec_length_1536(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting(
        db_session, user.id, title="Senior Backend Engineer", skills=["Python", "PostgreSQL"]
    )

    await embed_posting(posting, _deps())

    assert posting.title_vec is not None
    assert len(posting.title_vec) == 1536
    assert posting.skills_vec is not None
    assert len(posting.skills_vec) == 1536


@requires_db
async def test_embed_posting_noops_skills_vec_when_no_skills(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting(db_session, user.id, title="Designer", skills=[])

    await embed_posting(posting, _deps())

    assert posting.title_vec is not None
    assert posting.skills_vec is None


@requires_db
async def test_embed_posting_pseudo_vector_is_stable_for_same_text(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    first = await _make_posting(db_session, user.id, title="Backend Engineer", skills=["Python"])
    second = await _make_posting(db_session, user.id, title="Backend Engineer", skills=["Python"])

    await embed_posting(first, _deps())
    await embed_posting(second, _deps())

    assert first.title_vec == second.title_vec
    assert first.skills_vec == second.skills_vec
