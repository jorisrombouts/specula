from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Company, Lens, Posting, PostingState, Score
from specula_api.schemas.jobs import (
    Factors,
    JobOut,
    JobsResponseOut,
    JobStateIn,
    JobStateOut,
    LensSummaryOut,
)
from specula_api.services.dedup_view import collapse_duplicates
from specula_api.services.lens_filter import is_default_lens, lens_where

# Location factor by work mode (the lens-independent base). The location factor is
# LENS-AWARE (§6.2): re-derived per active lens at read time, never stored on `scores`.
_BASE_BY_MODE = {"Remote": 92, "Hybrid": 70, "On-site": 50}
_LOW_SKILL_THRESHOLD = 45
_LOW_SKILL_CAP = 72
_LOW_SKILL_RED_FLAG = "Low required-skill overlap"
NEW_WITHIN_DAYS = 7


def _clamp(n: float) -> int:
    return max(0, min(100, round(n)))


def derive_loc(
    work_mode: str | None,
    country: str | None,
    hq: str | None,
    *,
    is_default: bool,
    origin_rule: str | None,
) -> int:
    """Rule-based location fit of a posting against the active lens (§6.2). The default
    lens uses the work-mode base; the `foreign_hq` origin rule rewards a non-local HQ so
    switching lenses genuinely re-ranks the pool on location."""
    base = _BASE_BY_MODE.get(work_mode or "", 60)
    if is_default:
        return _clamp(base)
    factor = base
    if origin_rule == "foreign_hq":
        factor += 8 if (hq and country and hq != country) else -8
    elif origin_rule == "domestic_hq":
        factor += 8 if (hq and country and hq == country) else -8
    return _clamp(factor)


def score_match(
    factor_role: int, factor_skill: int, factor_loc: int, red_flag: str | None
) -> tuple[int, str | None]:
    """Weighted blend (role .4 / skill .4 / loc .2) plus the one-way red-flag penalty:
    very low skill overlap caps the match and flags it (§6.2)."""
    match = _clamp(0.4 * factor_role + 0.4 * factor_skill + 0.2 * factor_loc)
    if factor_skill < _LOW_SKILL_THRESHOLD:
        red_flag = red_flag or _LOW_SKILL_RED_FLAG
        match = min(match, _LOW_SKILL_CAP)
    return match, red_flag


def is_new(posted_at: date | None, today: date, within: int = NEW_WITHIN_DAYS) -> bool:
    """Derived at read time (never stored): a posting is 'new' if seen within `within`
    days. Drives the lens-summary `isNew` counts."""
    if posted_at is None:
        return False
    return (today - posted_at) <= timedelta(days=within)


_DEADLINE_NONE = 999  # sort postings without a stated deadline last
_ORIGIN_VERIFIED_MIN = 80


def _flag(country: str | None) -> str:
    if not country or len(country) != 2 or not country.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country.upper())


def _initials(name: str | None) -> str:
    if not name:
        return "—"
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def _deadline_days(deadline_at: date | None, today: date) -> int:
    if deadline_at is None:
        return _DEADLINE_NONE
    return (deadline_at - today).days


def _posted_label(posted_at: date | None, today: date) -> str:
    if posted_at is None:
        return "unknown"
    return f"{(today - posted_at).days}d ago"


def _to_job(
    posting: Posting,
    company: Company | None,
    score: Score,
    state: PostingState | None,
    *,
    lens: Lens | None,
    today: date,
) -> JobOut:
    loc = derive_loc(
        posting.work_mode,
        posting.country,
        posting.hq_country,
        is_default=is_default_lens(lens),
        origin_rule=lens.origin_rule if lens else None,
    )
    match, red_flag = score_match(score.factor_role, score.factor_skill, loc, score.red_flag)
    hq_conf = company.hq_confidence if company and company.hq_confidence is not None else 0
    return JobOut(
        id=str(posting.id),
        company=company.name if company else "—",
        logo=_initials(company.name if company else None),
        title=posting.title or "",
        city=posting.city or "",
        country=posting.country or "",
        hq=posting.hq_country or "",
        mode=posting.work_mode or "",
        flag=_flag(posting.country),
        match=match,
        factors=Factors(role=score.factor_role, skill=score.factor_skill, loc=loc),
        overlap=(score.overlap_matched, score.overlap_total),
        seniority=posting.seniority or "",
        edu=posting.education or "",
        deadline_days=_deadline_days(posting.deadline_at, today),
        salary=posting.salary_text,
        posted=_posted_label(posting.posted_at, today),
        status=state.status if state else None,
        is_new=is_new(posting.posted_at, today),
        still_open=bool(posting.still_open),
        origin_verified=hq_conf >= _ORIGIN_VERIFIED_MIN,
        hq_conf=hq_conf,
        red_flag=red_flag,
        stack=list(posting.required_skills),
        nice_to_have=list(posting.nice_to_have),
        visa=posting.visa or "",
        langs=list(posting.languages),
        contract=posting.contract or "",
        geo=posting.geo or "",
        confidence=posting.extraction_confidence or 0,
        dismiss_reason=state.dismiss_reason if state else None,
        responsibilities=list(posting.responsibilities),
        summary=posting.summary or "",
        rationale=score.rationale,
        source_url=posting.source_url,
    )


SORTS = {"match", "deadline", "new"}


def _sort_jobs(jobs: list[JobOut], sort: str) -> list[JobOut]:
    if sort == "deadline":
        return sorted(jobs, key=lambda j: j.deadline_days)
    if sort == "new":
        return sorted(jobs, key=lambda j: j.is_new, reverse=True)
    return sorted(jobs, key=lambda j: j.match, reverse=True)


def _pool_stmt(user_id: UUID) -> Select[tuple[Posting, Company, Score, PostingState]]:
    # Inner-join scores: the pool is the *scored* pool. Company + state are optional
    # (outer-joined) and may be None per row despite the static tuple type.
    return (
        select(Posting, Company, Score, PostingState)
        .join(Score, Score.posting_id == Posting.id)
        .outerjoin(Company, Company.id == Posting.company_id)
        .outerjoin(PostingState, PostingState.posting_id == Posting.id)
        .where(Posting.user_id == user_id)
    )


def _summarize(lens: Lens, count: int, new_count: int) -> LensSummaryOut:
    return LensSummaryOut(
        id=str(lens.id),
        name=lens.name,
        short=lens.short or "",
        active=bool(lens.active),
        scope=lens.scope or "",
        modes=list(lens.modes),
        origin=lens.origin_rule or "",
        focus=lens.focus or "",
        seeds=list(lens.seeds),
        count=count,
        is_new=new_count,
    )


async def list_jobs(
    session: AsyncSession, user_id: UUID, lens_id: str | None, sort: str
) -> JobsResponseOut:
    today = date.today()
    sort = sort if sort in SORTS else "match"
    lenses = list(
        await session.scalars(select(Lens).where(Lens.user_id == user_id).order_by(Lens.created_at))
    )
    selected = next((lens for lens in lenses if str(lens.id) == str(lens_id)), None)

    rows = (await session.execute(_pool_stmt(user_id).where(*lens_where(selected)))).all()
    # The pool is deduped on read (spec §5): one row per dedup_group, so the same role reaching
    # us from two sources shows once.
    rows = collapse_duplicates(rows, posting_of=lambda row: row[0])
    jobs = _sort_jobs(
        [_to_job(p, c, s, st, lens=selected, today=today) for p, c, s, st in rows], sort
    )

    # Per-lens derived counts: total + `isNew` in one round-trip via a FILTER clause.
    summaries: list[LensSummaryOut] = []
    new_cutoff = today - timedelta(days=NEW_WITHIN_DAYS)
    for lens in lenses:
        counts = (
            await session.execute(
                # Counted over dedup groups, not rows, so a duplicated role can't inflate a
                # lens badge past what the (deduped) list actually shows. An ungrouped posting
                # is its own group via the id fallback.
                select(
                    func.count(distinct(func.coalesce(Posting.dedup_group, Posting.id))).label(
                        "total"
                    ),
                    func.count(distinct(func.coalesce(Posting.dedup_group, Posting.id)))
                    .filter(Posting.posted_at >= new_cutoff)
                    .label("new_count"),
                )
                .select_from(Posting)
                .join(Score, Score.posting_id == Posting.id)
                .where(Posting.user_id == user_id, *lens_where(lens))
            )
        ).one()
        summaries.append(_summarize(lens, counts.total, counts.new_count))

    return JobsResponseOut(jobs=jobs, lenses=summaries, sort=sort)


async def get_job(session: AsyncSession, user_id: UUID, posting_id: UUID) -> JobOut | None:
    row = (await session.execute(_pool_stmt(user_id).where(Posting.id == posting_id))).first()
    if row is None:
        return None
    posting, company, score, state = row
    return _to_job(posting, company, score, state, lens=None, today=date.today())


async def upsert_state(
    session: AsyncSession, user_id: UUID, posting_id: UUID, data: JobStateIn
) -> JobStateOut | None:
    posting = await session.get(Posting, posting_id)
    if posting is None or posting.user_id != user_id:
        return None
    state = await session.get(PostingState, posting_id)
    if state is None:
        # Rule 6: carry user_id from the owning posting, never from client input.
        state = PostingState(posting_id=posting_id, user_id=posting.user_id)
        session.add(state)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(state, field, value)
    await session.flush()
    await session.refresh(state)  # load the server-side updated_at (onupdate) synchronously
    return JobStateOut.model_validate(state)
