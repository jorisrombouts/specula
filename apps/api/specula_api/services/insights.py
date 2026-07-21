"""Read-model aggregates over the user's postings. Everything here is DERIVED at read
time — nothing is a stored count. Product invariants enforced:
- low-confidence extractions are excluded from every aggregate;
- salary is display-only and never ranks/filters (there is no numeric salary in the
  data model, so the band list is empty until a salary parser exists);
- every query is scoped by `user_id` (belt-and-suspenders alongside RLS).
"""

from collections import Counter
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import CandidateProfile, Company, Posting
from specula_api.schemas.insights import (
    ActiveCompany,
    Insights,
    ModeMix,
    SeniorityMix,
    SkillDemand,
    SkillsGap,
    Trend,
    TrendSeries,
)
from specula_api.services.dedup_view import collapse_duplicates

# extraction_confidence below this is "surfaced, not trusted" — excluded everywhere.
LOW_CONFIDENCE_THRESHOLD = 50

_PERIOD_WEEKS = {"4w": 4, "8w": 8, "q": 13}
_PERIOD_LABELS = {"4w": "Last 4 weeks", "8w": "Last 8 weeks", "q": "This quarter"}
_MODE_COLORS = {"Remote": "var(--accent)", "Hybrid": "var(--ink)", "On-site": "var(--ink-3)"}
_TREND_COLORS = ["var(--accent)", "#9A7A18", "var(--ink-2)"]
_TOP_SKILLS = 8
_TREND_SERIES = 3


def _effective_date(p: Posting) -> date:
    return p.posted_at or p.first_seen_at.date()


def _is_trusted(p: Posting) -> bool:
    conf = p.extraction_confidence
    return conf is not None and conf >= LOW_CONFIDENCE_THRESHOLD


def _pct(n: int, total: int) -> int:
    return round(n / total * 100) if total else 0


async def _trusted_postings(session: AsyncSession, user_id: UUID) -> list[Posting]:
    """Trusted postings, deduped on read: a role listed by two sources is ONE role, so it must
    not count twice toward skill demand, the mix breakdowns or the trend."""
    rows = await session.scalars(select(Posting).where(Posting.user_id == user_id))
    return collapse_duplicates([p for p in rows if _is_trusted(p)])


async def _candidate_skills(session: AsyncSession, user_id: UUID) -> set[str]:
    profile = await session.get(CandidateProfile, user_id)
    return {s.casefold() for s in profile.skills} if profile else set()


def _skill_demand(
    postings: list[Posting], prior: list[Posting], have: set[str]
) -> list[SkillDemand]:
    counts = Counter(sk for p in postings for sk in set(p.required_skills))
    prior_counts = Counter(sk for p in prior for sk in set(p.required_skills))
    out = []
    for skill, n in counts.most_common():
        pct = _pct(n, len(postings))
        delta = pct - _pct(prior_counts.get(skill, 0), len(prior))
        out.append(
            SkillDemand(
                skill=skill,
                pct=pct,
                delta=delta,
                up=delta >= 0,
                gap=skill.casefold() not in have,
            )
        )
    out.sort(key=lambda s: (-s.pct, s.skill))
    return out[:_TOP_SKILLS]


def _trend(postings: list[Posting], demand: list[SkillDemand], start: date, weeks: int) -> Trend:
    labels = [f"w{i + 1}" for i in range(weeks)]
    series = []
    for idx, sd in enumerate(demand[:_TREND_SERIES]):
        data = [0] * weeks
        for p in postings:
            if sd.skill in p.required_skills:
                bucket = min((_effective_date(p) - start).days // 7, weeks - 1)
                data[bucket] += 1
        series.append(TrendSeries(name=sd.skill, color=_TREND_COLORS[idx], data=data))
    return Trend(weeks=labels, series=series)


def _mix(postings: list[Posting], attr: str) -> Counter[str]:
    return Counter(getattr(p, attr) for p in postings if getattr(p, attr))


async def compute_insights(session: AsyncSession, user_id: UUID, period: str) -> Insights:
    weeks = _PERIOD_WEEKS.get(period, _PERIOD_WEEKS["8w"])
    today = date.today()
    start = today - timedelta(weeks=weeks)
    prior_start = start - timedelta(weeks=weeks)

    trusted = await _trusted_postings(session, user_id)
    window = [p for p in trusted if start <= _effective_date(p) <= today]
    prior = [p for p in trusted if prior_start <= _effective_date(p) < start]
    low_conf_excluded = sum(
        1
        for p in await session.scalars(select(Posting).where(Posting.user_id == user_id))
        if not _is_trusted(p) and start <= _effective_date(p) <= today
    )

    have = await _candidate_skills(session, user_id)
    demand = _skill_demand(window, prior, have)

    seniority = _mix(window, "seniority")
    mode = _mix(window, "work_mode")

    companies = {
        c.id: c.name
        for c in await session.scalars(select(Company).where(Company.user_id == user_id))
    }
    company_counts = Counter(p.company_id for p in window if p.company_id is not None)

    return Insights(
        period=_PERIOD_LABELS.get(period, _PERIOD_LABELS["8w"]),
        total_analysed=len(window),
        low_conf_excluded=low_conf_excluded,
        skill_demand=demand,
        trend=_trend(window, demand, start, weeks),
        seniority_mix=[
            SeniorityMix(k=k, v=_pct(n, len(window)))
            for k, n in sorted(seniority.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        mode_mix=[
            ModeMix(k=k, v=_pct(n, len(window)), color=_MODE_COLORS.get(k, "var(--ink-2)"))
            for k, n in sorted(mode.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        salary=[],
        active_companies=[
            ActiveCompany(name=companies.get(cid, "—"), n=n)
            for cid, n in sorted(
                company_counts.items(), key=lambda kv: (-kv[1], companies.get(kv[0], ""))
            )
        ][:_TOP_SKILLS],
    )


async def compute_skills_gap(session: AsyncSession, user_id: UUID) -> list[SkillsGap]:
    trusted = await _trusted_postings(session, user_id)
    have = await _candidate_skills(session, user_id)

    counts = Counter(
        sk for p in trusted for sk in set(p.required_skills) if sk.casefold() not in have
    )
    gaps = [
        SkillsGap(
            skill=skill,
            roles=n,
            note=f"appears in {n} of your target roles, not on your profile",
        )
        for skill, n in counts.most_common()
    ]
    gaps.sort(key=lambda g: (-g.roles, g.skill))
    return gaps
