"""Fetch stage: crawl a tracked company's ATS/careers page into posting provenance shells.

Writes ONLY the provenance shell (source, source_url, content_hash, still_open,
first_seen_at, last_seen_at) plus change-detection/lifecycle bookkeeping. Every
extraction/insight field on `Posting` (title, required_skills, ..., title_vec, dedup_group)
is left at its NULL/default — that's the extract/embed/dedup/score stages' job.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Company, Posting, Targeting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.source import resolve_adapter
from specula_api.pipeline.util import title_matches_roles


class FetchResult(BaseModel):
    found: int = 0
    new: int = 0
    closed: int = 0
    errors: int = 0


async def fetch_postings(
    session: AsyncSession, user_id: UUID, company: Company, deps: PipelineDeps
) -> FetchResult:
    """List the company's current postings via its ATS adapter, upsert them as provenance
    shells, and close out postings that dropped off the listing.

    The adapter (`resolve_adapter(...).list_postings`) already returns `[]` rather than
    raising on 404/garbage/JS-shell responses, but this still wraps the call defensively —
    an adapter that *does* raise counts as `errors=1` and yields no raws, which matters for
    the lifecycle guard below.
    """
    try:
        raws = await resolve_adapter(company).list_postings(company, deps.fetcher)
        errors = 0
    except Exception:
        raws = []
        errors = 1

    # Narrow a big board to the user's target roles by feed title (cheap) before any
    # per-posting LLM extraction runs downstream.
    targeting = await session.get(Targeting, user_id)
    role_titles = targeting.role_titles if targeting is not None else []
    raws = [rp for rp in raws if title_matches_roles(rp.title_hint, role_titles)]

    now = deps.now()
    seen_hashes = {rp.content_hash for rp in raws}
    existing_by_hash = await _existing_by_hash(session, user_id, seen_hashes)

    new = 0
    for rp in raws:
        existing = existing_by_hash.get(rp.content_hash)
        if existing is not None:
            existing.last_seen_at = now
            existing.still_open = True
        else:
            session.add(
                Posting(
                    user_id=user_id,
                    company_id=company.id,
                    source=company.ats or "scrape",
                    source_url=rp.source_url,
                    content_hash=rp.content_hash,
                    still_open=True,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            new += 1

    # A fetch that raised tells us nothing about which postings are still open, so it must
    # not mass-close anything. A fetch that *succeeded* and legitimately came back empty
    # (`raws == []`, `errors == 0`) means the company has no open postings right now — that
    # correctly closes everything still marked open.
    closed = 0
    if raws or errors == 0:
        closed = await _close_stale(session, user_id, company.id, seen_hashes, now)

    await session.flush()
    return FetchResult(found=len(raws), new=new, closed=closed, errors=errors)


async def _existing_by_hash(
    session: AsyncSession, user_id: UUID, hashes: set[str]
) -> dict[str, Posting]:
    if not hashes:
        return {}
    rows = await session.scalars(
        select(Posting).where(Posting.user_id == user_id, Posting.content_hash.in_(hashes))
    )
    return {p.content_hash: p for p in rows}


async def _close_stale(
    session: AsyncSession,
    user_id: UUID,
    company_id: UUID,
    seen_hashes: set[str],
    now: datetime,
) -> int:
    stale = await session.scalars(
        select(Posting).where(
            Posting.user_id == user_id,
            Posting.company_id == company_id,
            Posting.still_open.is_(True),
            Posting.content_hash.not_in(seen_hashes),
        )
    )
    count = 0
    for posting in stale:
        posting.still_open = False
        count += 1
    return count
