"""Dedup stage: cluster postings that are the same role reaching us from several sources.

Spec §5: cluster on `(company, normalized_title)` trigram match AND `title_vec` cosine
similarity (~0.92), assign a shared `dedup_group`; the pool is then deduped on read
(`services/dedup_view.py`).

Clustering is WITHIN a company. Two companies advertising a similarly-titled role are two
different jobs — collapsing across companies would hide real openings, a far worse failure
than showing a duplicate.
"""

import re
import uuid
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Float, bindparam, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import settings
from specula_api.db.models import Posting

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace/punctuation to single spaces, trim."""
    return _NON_WORD.sub(" ", title.lower()).strip()


class _Clusters:
    """Union-find over posting ids, so A~B and B~C land in one group."""

    def __init__(self) -> None:
        self._parent: dict[UUID, UUID] = {}

    def find(self, item: UUID) -> UUID:
        self._parent.setdefault(item, item)
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, a: UUID, b: UUID) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_b] = root_a

    def groups(self) -> list[list[UUID]]:
        out: dict[UUID, list[UUID]] = {}
        for item in self._parent:
            out.setdefault(self.find(item), []).append(item)
        return [members for members in out.values() if len(members) > 1]


async def _similar_pairs(
    session: AsyncSession, user_id: UUID, company_id: UUID
) -> list[tuple[UUID, UUID]]:
    """Posting pairs the DB judges near-identical: pg_trgm on the title AND pgvector cosine.

    `a.id < b.id` keeps each pair once. Postings without a `title_vec` are skipped here — the
    exact-title pass in `dedup_company` still catches those.
    """
    a = Posting.__table__.alias("a")
    b = Posting.__table__.alias("b")
    cosine_distance = 1.0 - settings.dedup_vector_similarity
    join_on = (b.c.user_id == a.c.user_id) & (b.c.company_id == a.c.company_id) & (a.c.id < b.c.id)
    stmt = (
        select(a.c.id, b.c.id)
        .select_from(a.join(b, join_on))
        .where(
            a.c.user_id == user_id,
            a.c.company_id == company_id,
            a.c.title.is_not(None),
            b.c.title.is_not(None),
            a.c.title_vec.is_not(None),
            b.c.title_vec.is_not(None),
            func.similarity(a.c.title, b.c.title)
            >= bindparam("trgm", settings.dedup_title_similarity, type_=Float),
            a.c.title_vec.cosine_distance(b.c.title_vec)
            <= bindparam("cos", cosine_distance, type_=Float),
            # Different stated seniority means different openings, not one role seen twice.
            # Trigram alone pairs them: "Data Scientist" vs "Senior Data Scientist" matches
            # at 0.71. Whether the cosine gate would also catch that exact pair is UNKNOWN —
            # bare "Data Scientist" isn't in the recorded corpus. The nearest pair we can
            # measure, "Data Scientist, Applied Science" vs "Senior Data Scientist", embeds
            # at 0.68 (test_dedup.py), but it differs in specialization as well as seniority,
            # so it does not settle the question. For scale, those same two roles' SKILLS
            # vectors sit at 0.90 — real distinct roles do get close to the 0.92 gate. This
            # guard is therefore not known to be redundant, and merging two real openings is
            # the worst failure this stage has. It stays.
            (a.c.seniority.is_(None))
            | (b.c.seniority.is_(None))
            | (func.lower(a.c.seniority) == func.lower(b.c.seniority)),
        )
    )
    return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]


async def dedup_company(session: AsyncSession, user_id: UUID, company_id: UUID) -> None:
    """Assign a shared `dedup_group` to this company's same-role postings.

    Two passes, unioned: an exact normalized-title match (which needs no embedding, so it
    still works for postings that were never embedded), and the trigram+cosine pass above for
    near-matches such as "Senior ML Engineer" vs "Senior Machine Learning Engineer".

    Reruns reuse an existing group's id when any member already carries one, so group identity
    is stable across ingests.
    """
    postings = list(
        await session.scalars(
            select(Posting).where(
                Posting.user_id == user_id,
                Posting.company_id == company_id,
                Posting.title.is_not(None),
            )
        )
    )
    if len(postings) < 2:
        return

    by_id = {posting.id: posting for posting in postings}
    clusters = _Clusters()

    by_title: dict[str, list[UUID]] = {}
    for posting in postings:
        by_title.setdefault(normalize_title(posting.title or ""), []).append(posting.id)
    for ids in by_title.values():
        for other in ids[1:]:
            clusters.union(ids[0], other)

    for left, right in await _similar_pairs(session, user_id, company_id):
        clusters.union(left, right)

    for members in clusters.groups():
        group: Sequence[Posting] = [by_id[item] for item in members if item in by_id]
        existing = next((p.dedup_group for p in group if p.dedup_group is not None), None)
        group_id = existing or uuid.uuid4()
        for posting in group:
            posting.dedup_group = group_id

    await session.flush()
