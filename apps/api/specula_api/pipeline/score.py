"""Score stage: salary-blind hybrid scoring (§6.2).

`factor_role`/`factor_skill`/overlap are computed deterministically from embeddings and
taxonomy-aware skill overlap; the LLM only narrates the computed numbers into
`rationale` — never the reverse. `factor_loc` and the overall `match` index are
lens-aware and derived at READ time (`services/jobs.py`) — never computed or stored
here. `posting.salary_text` is never read by this module.
"""

import math
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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


def _vector_provenance(deps: PipelineDeps) -> str:
    """What produced a cached vector — the cache is only valid within one provenance.

    `recorded` mode returns deterministic PSEUDO-vectors for any text without a recorded
    fixture (see openai_client._pseudo_vector); they carry no semantics, and this table is
    GLOBAL and unscoped, so a test run would otherwise poison live scoring permanently.
    Naming the model for real embeddings covers the other direction: switching
    `openai_embed_model` puts vectors in a different space, and stale ones must not be
    silently reused.
    """
    if deps.settings.pipeline_mode == "recorded":
        return "recorded"
    return deps.settings.openai_embed_model


async def skill_vectors(
    session: AsyncSession, canonical_skills: set[str], deps: PipelineDeps
) -> dict[str, list[float]]:
    """Embedding per canonical skill, cached GLOBALLY in `skills_taxonomy.vec`.

    Skills repeat heavily across postings ("Python" appears in most of them), so embedding
    per posting would pay for the same vector hundreds of times. The cache is keyed by the
    canonical form, which means an aliased skill resolves to the same entry — and therefore
    the same vector — as its canonical name, so exact and aliased matches compare at cosine
    1.0 without a separate string-matching code path.

    Only vectors from the CURRENT provenance are reused (see `_vector_provenance`); anything
    else is re-embedded and overwritten, so the cache is self-healing.

    Writes through `skills_taxonomy`, which also holds hand-curated aliases: the upsert
    touches `vec`/`vec_model` ONLY, so filling in a vector never clobbers them.
    """
    if not canonical_skills:
        return {}

    provenance = _vector_provenance(deps)
    rows = await session.scalars(
        select(SkillsTaxonomy).where(
            SkillsTaxonomy.canonical.in_(canonical_skills),
            SkillsTaxonomy.vec_model == provenance,
        )
    )
    vectors = {row.canonical: row.vec for row in rows if row.vec is not None}

    missing = sorted(canonical_skills - set(vectors))
    if missing:
        embedded = await deps.openai.embed(missing)
        vectors.update(zip(missing, embedded, strict=True))
        statement = pg_insert(SkillsTaxonomy).values(
            [
                {"canonical": skill, "vec": vectors[skill], "vec_model": provenance}
                for skill in missing
            ]
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[SkillsTaxonomy.canonical],
                set_={"vec": statement.excluded.vec, "vec_model": statement.excluded.vec_model},
            )
        )

    return vectors


def semantic_overlap(
    required_vecs: list[list[float]], candidate_vecs: list[list[float]], *, threshold: float
) -> int:
    """How many required skills the candidate covers: a requirement counts once when its
    cosine to ANY candidate skill clears `threshold`.

    Per-requirement, so one broad candidate skill may legitimately cover several
    requirements and is never "used up" by the first one it matches.
    """
    return sum(
        1
        for required in required_vecs
        if any(cosine(required, candidate) >= threshold for candidate in candidate_vecs)
    )


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
    must_haves: list[str],
    must_have_vecs: Sequence[list[float]],
    required_vecs: list[list[float]],
    *,
    threshold: float,
) -> str | None:
    """The first `targeting.must_haves` entry no required skill covers, or None.

    A must-have is a SKILL, compared against the posting's skills exactly like overlap —
    one register, one comparison. Measured on the live corpus that comparison separates
    cleanly: most postings that list the skill hit exactly 1.00, and there is an empty gap
    between the highest false positive ("sql" covers "python" at 0.477) and the lowest true
    match ("python engineering", 0.617). `must_have_similarity` sits in that gap.

    Deliberately NOT supported: criteria about the role as a whole ("Production ML or
    applied LLM work"). Whether a posting satisfies one is an ENTAILMENT question, and
    cosine measures topical similarity. Tried against skill tokens, against the aggregate
    skills vector, and against the full title/summary/responsibilities text — every one
    produced a smooth ramp with no separating boundary. Against profile text, postings that
    require Python scored 0.106-0.207 while those that don't scored 0.090-0.182: fully
    overlapping. Any threshold there would be fitted to noise. Free-text criteria belong in
    `targeting.preferences`, which does not drive scoring.

    Exact string matching previously flagged 53 of 53 postings, because prose can never
    appear verbatim in a skills list. The flag renders in the UI and is fed to the rationale
    writer, so a permanently-on false warning was shaping every rationale in the product.

    This is the ONLY red_flag this stage sets — the low-skill-overlap flag belongs to the
    read model (`services/jobs.py::score_match`).
    """
    for must_have, must_have_vec in zip(must_haves, must_have_vecs, strict=True):
        if not any(cosine(must_have_vec, vec) >= threshold for vec in required_vecs):
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
    must_have_vecs: Sequence[list[float]],
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
    # Skills are compared as embeddings, not strings. String equality counted a requirement
    # as met only when both sides happened to word it identically, so a candidate with
    # PyTorch and scikit-learn scored zero against "Machine Learning" — every posting in the
    # pool landed on the same 2 matches (Python, SQL) and tripped the read model's
    # low-overlap red flag. Identical/aliased skills share one canonical cache entry and so
    # still compare at exactly 1.0; the threshold only governs the semantic tail.
    vectors = await skill_vectors(session, required_canon | candidate_canon, deps)
    required_vecs = [vectors[skill] for skill in required_canon if skill in vectors]
    overlap_matched = semantic_overlap(
        required_vecs,
        [vectors[skill] for skill in candidate_canon if skill in vectors],
        threshold=deps.settings.skill_match_similarity,
    )
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

    red_flag = _missing_must_have(
        targeting.must_haves,
        must_have_vecs,
        required_vecs,
        threshold=deps.settings.must_have_similarity,
    )

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
