from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.db.models import Company, Posting
from specula_api.pipeline.dedup import dedup_company, normalize_title


class TestNormalizeTitle:
    def test_lowercases_and_collapses_whitespace_and_punctuation(self) -> None:
        assert normalize_title("  Senior   ML Engineer! ") == "senior ml engineer"

    def test_equivalent_titles_normalize_equal(self) -> None:
        assert normalize_title("Senior ML Engineer") == normalize_title("senior--ml,engineer")

    def test_different_titles_normalize_different(self) -> None:
        assert normalize_title("Backend Engineer") != normalize_title("ML Engineer")


async def _make_company(session: AsyncSession, user_id: object) -> Company:
    company = Company(user_id=user_id, name="Acme", domain="acme.com")
    session.add(company)
    await session.flush()
    return company


async def _make_posting(
    session: AsyncSession, user_id: object, company: Company, *, title: str | None, url: str
) -> Posting:
    posting = Posting(
        user_id=user_id,
        company_id=company.id,
        source="scrape",
        source_url=url,
        content_hash=f"hash-{url}",
        title=title,
    )
    session.add(posting)
    await session.flush()
    return posting


# --- dedup_company ----------------------------------------------------------------


@requires_db
async def test_dedup_company_groups_postings_sharing_normalized_title(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    same_1 = await _make_posting(
        db_session, user.id, company, title="Senior ML Engineer", url="https://acme.com/1"
    )
    same_2 = await _make_posting(
        db_session, user.id, company, title="senior, ml   engineer!", url="https://acme.com/2"
    )
    distinct = await _make_posting(
        db_session, user.id, company, title="Backend Engineer", url="https://acme.com/3"
    )

    await dedup_company(db_session, user.id, company.id)

    assert same_1.dedup_group is not None
    assert same_1.dedup_group == same_2.dedup_group
    assert distinct.dedup_group is None  # unique title within the company — no group needed


@requires_db
async def test_dedup_company_does_not_group_across_different_companies(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company_a = await _make_company(db_session, user.id)
    company_b = Company(user_id=user.id, name="Beta", domain="beta.com")
    db_session.add(company_b)
    await db_session.flush()

    in_a = await _make_posting(
        db_session, user.id, company_a, title="ML Engineer", url="https://acme.com/1"
    )
    in_b = await _make_posting(
        db_session, user.id, company_b, title="ML Engineer", url="https://beta.com/1"
    )

    await dedup_company(db_session, user.id, company_a.id)
    await dedup_company(db_session, user.id, company_b.id)

    # Same normalized title, but different companies — dedup_company is scoped per-company.
    assert in_a.dedup_group is None
    assert in_b.dedup_group is None


@requires_db
async def test_dedup_company_ignores_postings_without_a_title_yet(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    shell = await _make_posting(db_session, user.id, company, title=None, url="https://acme.com/1")

    await dedup_company(db_session, user.id, company.id)

    assert shell.dedup_group is None


@requires_db
async def test_dedup_company_group_id_is_stable_across_reruns(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    first = await _make_posting(
        db_session, user.id, company, title="ML Engineer", url="https://acme.com/1"
    )
    second = await _make_posting(
        db_session, user.id, company, title="ML Engineer", url="https://acme.com/2"
    )

    await dedup_company(db_session, user.id, company.id)
    group_id = first.dedup_group
    assert group_id is not None

    # A third posting with the same title joins on the next run — the earlier group id
    # is preserved rather than minting a new one for the whole group.
    third = await _make_posting(
        db_session, user.id, company, title="ML Engineer", url="https://acme.com/3"
    )
    await dedup_company(db_session, user.id, company.id)

    assert first.dedup_group == group_id
    assert second.dedup_group == group_id
    assert third.dedup_group == group_id


@requires_db
async def test_dedup_company_is_idempotent_no_dup_rows(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    await _make_posting(db_session, user.id, company, title="ML Engineer", url="https://acme.com/1")
    await _make_posting(db_session, user.id, company, title="ML Engineer", url="https://acme.com/2")

    await dedup_company(db_session, user.id, company.id)
    await dedup_company(db_session, user.id, company.id)
    await dedup_company(db_session, user.id, company.id)

    postings = (
        await db_session.scalars(select(Posting).where(Posting.company_id == company.id))
    ).all()
    assert len(postings) == 2
