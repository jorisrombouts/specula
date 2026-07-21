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


# --- trigram + cosine clustering (spec §5) ----------------------------------------


def _vec(offset: float) -> list[float]:
    """A unit-ish 1536-d vector; `offset` tilts it away from the base direction.

    cos(_vec(0), _vec(0.1)) ~= 0.995 (clears 0.92); cos(_vec(0), _vec(1.0)) ~= 0.707 (does not).
    """
    v = [0.0] * 1536
    v[0] = 1.0
    v[1] = offset
    return v


async def _embedded(
    session: AsyncSession,
    user_id: object,
    company: Company,
    *,
    title: str,
    url: str,
    offset: float,
    seniority: str | None = None,
) -> Posting:
    posting = await _make_posting(session, user_id, company, title=title, url=url)
    posting.title_vec = _vec(offset)
    posting.seniority = seniority
    await session.flush()
    return posting


@requires_db
async def test_near_identical_titles_with_close_vectors_are_grouped(
    db_session: AsyncSession,
) -> None:
    """The case exact-title matching misses: one role, two sources wording it differently."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    a = await _embedded(
        db_session, user.id, company, title="Senior ML Engineer", url="u1", offset=0.0
    )
    b = await _embedded(
        db_session, user.id, company, title="Senior ML Engineer (Remote)", url="u2", offset=0.1
    )

    await dedup_company(db_session, user.id, company.id)

    assert a.dedup_group is not None
    assert a.dedup_group == b.dedup_group


@requires_db
async def test_lexically_similar_titles_with_distant_vectors_are_not_grouped(
    db_session: AsyncSession,
) -> None:
    """Trigram alone would pair these; the cosine gate is what keeps them apart."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    a = await _embedded(
        db_session, user.id, company, title="Engineering Manager", url="u1", offset=0.0
    )
    b = await _embedded(db_session, user.id, company, title="Engineer", url="u2", offset=1.0)

    await dedup_company(db_session, user.id, company.id)

    assert a.dedup_group is None
    assert b.dedup_group is None


@requires_db
async def test_different_seniority_is_never_merged(db_session: AsyncSession) -> None:
    """ "Data Scientist" vs "Senior Data Scientist" trigram-matches at 0.71 and embeds
    near-identically, so neither spec threshold separates them — but they are two distinct
    openings. Merging would hide a real job, the worst failure mode for this stage."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    mid = await _embedded(
        db_session, user.id, company, title="Data Scientist", url="u1", offset=0.0, seniority="mid"
    )
    senior = await _embedded(
        db_session,
        user.id,
        company,
        title="Senior Data Scientist",
        url="u2",
        offset=0.01,
        seniority="senior",
    )

    await dedup_company(db_session, user.id, company.id)

    assert mid.dedup_group is None
    assert senior.dedup_group is None


@requires_db
async def test_clustering_is_transitive_across_sources(db_session: AsyncSession) -> None:
    """A~B and B~C must land in ONE group, not two overlapping pairs."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    a = await _embedded(db_session, user.id, company, title="ML Engineer", url="u1", offset=0.0)
    b = await _embedded(
        db_session, user.id, company, title="ML Engineer (Remote)", url="u2", offset=0.02
    )
    c = await _embedded(
        db_session, user.id, company, title="ML Engineer - Remote", url="u3", offset=0.04
    )

    await dedup_company(db_session, user.id, company.id)

    assert a.dedup_group is not None
    assert a.dedup_group == b.dedup_group == c.dedup_group


@requires_db
async def test_postings_at_different_companies_are_never_grouped(
    db_session: AsyncSession,
) -> None:
    """Two companies hiring the same-titled role are two real openings."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    acme = await _make_company(db_session, user.id)
    other = Company(user_id=user.id, name="Other", domain="other.example")
    db_session.add(other)
    await db_session.flush()
    a = await _embedded(db_session, user.id, acme, title="ML Engineer", url="u1", offset=0.0)
    b = await _embedded(db_session, user.id, other, title="ML Engineer", url="u2", offset=0.0)

    await dedup_company(db_session, user.id, acme.id)
    await dedup_company(db_session, user.id, other.id)

    assert a.dedup_group is None
    assert b.dedup_group is None
