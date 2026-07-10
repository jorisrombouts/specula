"""Dedup stage: minimal same-company title grouping.

# TODO(M3.x): trigram + title_vec cosine clustering across companies/sources — this
# minimal pass only groups postings within one company that share an exact normalized
# title.
"""

import re
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Posting

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace/punctuation to single spaces, trim."""
    return _NON_WORD.sub(" ", title.lower()).strip()


async def dedup_company(session: AsyncSession, user_id: UUID, company_id: UUID) -> None:
    """Group this company's postings sharing a normalized title into a shared dedup_group.

    Minimal grouping; # TODO(M3.x): trigram + title_vec cosine clustering across
    companies/sources. Titles unique within the company are left ungrouped
    (dedup_group stays None). Reruns reuse an existing group's id when any member
    already has one, so group identity is stable across ingests.
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
    groups: dict[str, list[Posting]] = {}
    for posting in postings:
        key = normalize_title(posting.title or "")
        groups.setdefault(key, []).append(posting)

    for group in groups.values():
        if len(group) < 2:
            continue
        existing = next((p.dedup_group for p in group if p.dedup_group is not None), None)
        group_id = existing or uuid.uuid4()
        for posting in group:
            posting.dedup_group = group_id

    await session.flush()
