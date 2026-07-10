"""Score stage: salary-blind hybrid scoring (§6.2).

`factor_role`/`factor_skill`/overlap are computed deterministically from embeddings and
taxonomy-aware skill overlap; the LLM only narrates the computed numbers into
`rationale` — never the reverse. `factor_loc` and the overall `match` index are
lens-aware and derived at READ time (`services/jobs.py`) — never computed or stored
here. `posting.salary_text` is never read by this module.
"""

import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import CandidateProfile, Posting, Score, SkillsTaxonomy, Targeting
from specula_api.pipeline.deps import PipelineDeps

_SKILL_OVERLAP_WEIGHT = 0.6
_SKILL_COSINE_WEIGHT = 0.4
_SENIORITY_BONUS = 5
_SENIORITY_PENALTY = 5


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Cosine similarity in [-1, 1]. 0.0 if either vector is missing or zero-length.
    Pure-python — no numpy dependency."""
    if a is None or b is None:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


async def _alias_map(session: AsyncSession) -> dict[str, str]:
    """casefolded alias/canonical text -> casefolded canonical skill name, from the
    global `skills_taxonomy` table."""
    rows = await session.scalars(select(SkillsTaxonomy))
    mapping: dict[str, str] = {}
    for row in rows:
        canonical = row.canonical.strip().casefold()
        mapping[canonical] = canonical
        for alias in row.aliases:
            mapping[alias.strip().casefold()] = canonical
    return mapping


def _canonicalize(skill: str, alias_map: dict[str, str]) -> str:
    key = skill.strip().casefold()
    return alias_map.get(key, key)


def _canon_set(skills: list[str], alias_map: dict[str, str]) -> set[str]:
    return {_canonicalize(s, alias_map) for s in skills if s.strip()}


def _seniority_adjustment(posting_seniority: str | None, targeting_seniority: list[str]) -> int:
    """Small bonus/penalty comparing the posting's seniority to the candidate's targeted
    seniority levels. Neutral (0) when either side has nothing to compare."""
    if not posting_seniority or not targeting_seniority:
        return 0
    wanted = {s.strip().casefold() for s in targeting_seniority}
    if posting_seniority.strip().casefold() in wanted:
        return _SENIORITY_BONUS
    return -_SENIORITY_PENALTY


def _missing_must_have(
    must_haves: list[str], required_canon: set[str], alias_map: dict[str, str]
) -> str | None:
    """The first `targeting.must_haves` entry absent from the posting's required skills,
    or None if all are present. This is the ONLY red_flag this stage sets — the
    low-skill-overlap flag belongs to the read model (`services/jobs.py::score_match`)."""
    for must_have in must_haves:
        if _canonicalize(must_have, alias_map) not in required_canon:
            return f"Missing must-have: {must_have}"
    return None


async def ensure_candidate_vectors(
    session: AsyncSession, candidate: CandidateProfile, deps: PipelineDeps
) -> None:
    """Embed candidate.skills -> candidate.skills_vec if NULL (persisted). No-op if
    already set or the candidate has no skills."""
    if candidate.skills_vec is not None or not candidate.skills:
        return
    [vec] = await deps.openai.embed([" ".join(candidate.skills)])
    candidate.skills_vec = vec
    await session.flush()


async def score_posting(
    session: AsyncSession,
    user_id: UUID,
    posting: Posting,
    candidate: CandidateProfile,
    targeting: Targeting,
    role_titles_vec: list[float] | None,
    deps: PipelineDeps,
) -> Score:
    """Compute the salary-blind hybrid score for one posting and upsert its `Score` row
    (PK `posting_id`). Idempotent — rerunning overwrites the same row, never inserts a
    duplicate."""
    # SERVICE OBLIGATION (db/models/score.py): scores.user_id always tracks the posting
    # being scored, never caller input — this only confirms the two already agree.
    assert posting.user_id == user_id, "score_posting: posting.user_id must match user_id"

    alias_map = await _alias_map(session)
    required_canon = _canon_set(posting.required_skills, alias_map)
    candidate_canon = _canon_set(candidate.skills, alias_map)
    matched = required_canon & candidate_canon
    overlap_matched = len(matched)
    overlap_total = len(required_canon)
    overlap_pct = (overlap_matched / overlap_total * 100) if overlap_total else 0.0

    skill_cosine_pct = cosine(posting.skills_vec, candidate.skills_vec) * 100
    factor_skill = _clamp(
        _SKILL_OVERLAP_WEIGHT * overlap_pct + _SKILL_COSINE_WEIGHT * skill_cosine_pct
    )

    role_cosine_pct = cosine(posting.title_vec, role_titles_vec) * 100
    factor_role = _clamp(
        role_cosine_pct + _seniority_adjustment(posting.seniority, targeting.seniority)
    )

    red_flag = _missing_must_have(targeting.must_haves, required_canon, alias_map)

    rationale = await deps.openai.rationale(
        factors={"role": factor_role, "skill": factor_skill},
        overlap=(overlap_matched, overlap_total),
        red_flag=red_flag,
    )

    scored_with = (
        f"{deps.settings.openai_extract_model}+{deps.settings.openai_embed_model}"
        f"/{deps.settings.scoring_version}"
    )

    score = await session.get(Score, posting.id)
    if score is None:
        score = Score(posting_id=posting.id)
        session.add(score)
    score.user_id = posting.user_id
    score.factor_role = factor_role
    score.factor_skill = factor_skill
    score.overlap_matched = overlap_matched
    score.overlap_total = overlap_total
    score.red_flag = red_flag
    score.rationale = rationale
    score.scored_with = scored_with
    score.scored_at = deps.now()
    await session.flush()
    return score
