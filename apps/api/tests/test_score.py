from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from conftest import make_user, set_tenant
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import (
    CandidateProfile,
    Company,
    Posting,
    Run,
    Score,
    SkillsTaxonomy,
    Targeting,
)
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.embeddings import embed_posting
from specula_api.pipeline.http import FetchedDoc
from specula_api.pipeline.openai_client import (
    EnrichResult,
    ExtractionResult,
    RecordedOpenAIClient,
    Source,
)
from specula_api.pipeline.score import (
    cosine,
    ensure_candidate_vectors,
    score_posting,
    semantic_overlap,
    skill_vectors,
)
from specula_api.services.jobs import get_job
from specula_api.services.run import create_run, ingest_company, latest_run, rescore_all

# A realistic posting page: extraction now requires meaningfully readable text, so a
# two-word stub would (correctly) be treated as an unextractable shell.
_JOB_PAGE_TEXT = (
    "Senior Backend Engineer at Acme Corp. We are hiring a senior backend engineer to "
    "join our platform team in Berlin. You will design and operate distributed services, "
    "own critical APIs end to end, and partner closely with product and data. "
    "Requirements: five or more years building production backends, strong Python and "
    "SQL, experience with asynchronous services and cloud infrastructure. Nice to have: "
    "Kubernetes and event-driven architectures."
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"


class _EchoingOpenAI:
    """Hand-built OpenAIClient stub: `embed` delegates to RecordedOpenAIClient's
    deterministic pseudo-vector fallback (no per-string fixtures needed), and
    `rationale` echoes the computed factors/overlap/red_flag verbatim so tests can
    assert the prose is DERIVED FROM the numbers, never the reverse."""

    def __init__(self) -> None:
        self._recorded = RecordedOpenAIClient(FIXTURES_DIR)
        self.rationale_calls: list[dict[str, object]] = []

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        raise NotImplementedError

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        raise NotImplementedError

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        raise NotImplementedError

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._recorded.embed(texts)

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
        raise NotImplementedError

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        self.rationale_calls.append(
            {"factors": dict(factors), "overlap": overlap, "red_flag": red_flag}
        )
        return (
            f"role={factors['role']} skill={factors['skill']} "
            f"overlap={overlap[0]}/{overlap[1]} red_flag={red_flag or 'none'}"
        )

    async def aclose(self) -> None:
        return None


def _deps(openai: _EchoingOpenAI) -> PipelineDeps:
    # pipeline_mode="recorded" pins the skill-vector cache to the "recorded" provenance.
    # Settings() otherwise reads .env, and a dev database shared with live runs holds REAL
    # cached vectors — skill_vectors would serve those while the stub returns pseudo-vectors
    # for everything else, so identical text would compare at ~0 instead of 1.0.
    return PipelineDeps(
        openai=openai,
        fetcher=_UnusedFetcher(),
        settings=Settings(pipeline_mode="recorded"),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )


async def _must_have_vecs(deps: PipelineDeps, targeting: Targeting) -> list[list[float]]:
    """Mirrors what `ingest_company` computes once per run."""
    return await deps.openai.embed(
        [must_have.strip().casefold() for must_have in targeting.must_haves]
    )


class _UnusedFetcher:
    """score_posting/ensure_candidate_vectors never touch the fetcher."""

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


async def _make_candidate(
    session: AsyncSession, user_id: UUID, *, skills: list[str]
) -> CandidateProfile:
    candidate = CandidateProfile(user_id=user_id, skills=skills)
    session.add(candidate)
    await session.flush()
    return candidate


async def _make_targeting(
    session: AsyncSession,
    user_id: UUID,
    *,
    role_titles: list[str],
    seniority: list[str] | None = None,
    must_haves: list[str] | None = None,
) -> Targeting:
    targeting = Targeting(
        user_id=user_id,
        role_titles=role_titles,
        seniority=seniority or [],
        must_haves=must_haves or [],
    )
    session.add(targeting)
    await session.flush()
    return targeting


async def _make_posting(
    session: AsyncSession,
    user_id: UUID,
    *,
    title: str,
    required_skills: list[str],
    seniority: str | None = None,
    salary_text: str | None = None,
    extraction_confidence: int = 90,
) -> Posting:
    external_id = uuid4()
    posting = Posting(
        user_id=user_id,
        source="scrape",
        source_url=f"https://acme.com/jobs/{external_id}",
        content_hash=f"hash-{external_id}",
        title=title,
        required_skills=required_skills,
        seniority=seniority,
        salary_text=salary_text,
        extraction_confidence=extraction_confidence,
    )
    session.add(posting)
    await session.flush()
    return posting


async def _role_titles_vec(deps: PipelineDeps, targeting: Targeting) -> list[float]:
    [vec] = await deps.openai.embed([" ".join(targeting.role_titles)])
    return vec


async def _score(
    session: AsyncSession,
    user_id: UUID,
    posting: Posting,
    candidate: CandidateProfile,
    targeting: Targeting,
    deps: PipelineDeps,
) -> Score:
    """Prep vectors the way `ingest_company` does, then call `score_posting`."""
    await embed_posting(posting, deps)
    await ensure_candidate_vectors(session, candidate, deps)
    role_titles_vec = await _role_titles_vec(deps, targeting)
    must_have_vecs = await _must_have_vecs(deps, targeting)
    return await score_posting(
        session, user_id, posting, candidate, targeting, role_titles_vec, must_have_vecs, deps
    )


# --- cosine (pure) ------------------------------------------------------------------


class TestCosine:
    def test_identical_vectors_is_one(self) -> None:
        assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors_is_zero(self) -> None:
        assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_opposite_vectors_is_negative_one(self) -> None:
        assert cosine([1.0, 0.0], [-1.0, 0.0]) == -1.0

    def test_either_none_is_zero(self) -> None:
        assert cosine(None, [1.0, 0.0]) == 0.0
        assert cosine([1.0, 0.0], None) == 0.0
        assert cosine(None, None) == 0.0

    def test_zero_vector_is_zero_not_a_division_error(self) -> None:
        assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


# --- semantic_overlap (pure) ----------------------------------------------------------
#
# Hand-built 2-D vectors, not embeddings: these assert the MATCHING RULE (max cosine over
# candidates vs threshold), which must hold whatever the embedding space looks like.

_THRESHOLD = 0.55


class TestSemanticOverlap:
    def test_identical_vectors_count_as_covered(self) -> None:
        # The exact/aliased case: one canonical cache entry -> the same vector on both
        # sides -> cosine 1.0. Exact matching is subsumed, not bolted on beside.
        assert semantic_overlap([[1.0, 0.0]], [[1.0, 0.0]], threshold=_THRESHOLD) == 1

    def test_orthogonal_vectors_are_not_covered(self) -> None:
        assert semantic_overlap([[1.0, 0.0]], [[0.0, 1.0]], threshold=_THRESHOLD) == 0

    def test_near_neighbour_above_threshold_is_covered(self) -> None:
        # cos(45 deg) = 0.707 >= 0.55: "Machine Learning" covered by "PyTorch".
        assert semantic_overlap([[1.0, 0.0]], [[1.0, 1.0]], threshold=_THRESHOLD) == 1

    def test_near_neighbour_below_threshold_is_not_covered(self) -> None:
        # cos(~76 deg) = 0.243 < 0.55: related-but-distinct stays a miss.
        assert semantic_overlap([[1.0, 0.0]], [[1.0, 4.0]], threshold=_THRESHOLD) == 0

    def test_requirement_matches_its_best_candidate_not_the_first(self) -> None:
        required = [[1.0, 0.0]]
        candidates = [[0.0, 1.0], [-1.0, 0.0], [1.0, 0.0]]  # only the last one covers it
        assert semantic_overlap(required, candidates, threshold=_THRESHOLD) == 1

    def test_one_candidate_may_cover_several_requirements(self) -> None:
        # A generalist skill legitimately covers more than one requirement — the count is
        # per REQUIREMENT, so candidates are never "used up".
        required = [[1.0, 0.0], [1.0, 0.1], [0.0, 1.0]]
        assert semantic_overlap(required, [[1.0, 0.0]], threshold=_THRESHOLD) == 2

    def test_counts_each_requirement_at_most_once(self) -> None:
        required = [[1.0, 0.0]]
        assert semantic_overlap(required, [[1.0, 0.0], [1.0, 0.0]], threshold=_THRESHOLD) == 1

    def test_empty_sides_are_zero_not_an_error(self) -> None:
        assert semantic_overlap([], [[1.0, 0.0]], threshold=_THRESHOLD) == 0
        assert semantic_overlap([[1.0, 0.0]], [], threshold=_THRESHOLD) == 0
        assert semantic_overlap([], [], threshold=_THRESHOLD) == 0


# --- skill_vectors (global embedding cache) -------------------------------------------


class _CountingOpenAI(_EchoingOpenAI):
    """Counts embed calls and the texts they carried, so the cache can be proven to
    actually prevent the second round trip."""

    def __init__(self) -> None:
        super().__init__()
        self.embedded: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.append(list(texts))
        return await super().embed(texts)


def _unique_skill(prefix: str) -> str:
    """`skills_taxonomy` is a GLOBAL unscoped table, so a fixed name like "python" would
    collide with committed rows (the demo seeder writes some). Same guard as
    test_score_posting_uses_taxonomy_aliases_for_overlap."""
    return f"{prefix}-{uuid4()}"


@requires_db
async def test_skill_vectors_embeds_each_distinct_skill_once(db_session: AsyncSession) -> None:
    one, two = _unique_skill("python"), _unique_skill("pytorch")
    openai = _CountingOpenAI()

    vectors = await skill_vectors(db_session, {one, two}, _deps(openai))

    assert set(vectors) == {one, two}
    assert sorted(openai.embedded[0]) == sorted([one, two])
    assert len(openai.embedded) == 1, "distinct skills must batch into ONE embed call"


@requires_db
async def test_skill_vectors_second_call_hits_the_cache(db_session: AsyncSession) -> None:
    one, two = _unique_skill("python"), _unique_skill("pytorch")
    await skill_vectors(db_session, {one, two}, _deps(_CountingOpenAI()))

    second = _CountingOpenAI()
    vectors = await skill_vectors(db_session, {one, two}, _deps(second))

    assert set(vectors) == {one, two}
    assert second.embedded == [], "cached skills must not be re-embedded"


@requires_db
async def test_skill_vectors_embeds_only_the_uncached_skills(db_session: AsyncSession) -> None:
    cached, fresh = _unique_skill("python"), _unique_skill("rust")
    await skill_vectors(db_session, {cached}, _deps(_CountingOpenAI()))

    openai = _CountingOpenAI()
    await skill_vectors(db_session, {cached, fresh}, _deps(openai))

    assert openai.embedded == [[fresh]]


def _deps_with(openai: _EchoingOpenAI, **overrides: object) -> PipelineDeps:
    return PipelineDeps(
        openai=openai,
        fetcher=_UnusedFetcher(),
        settings=Settings(**overrides),  # type: ignore[arg-type]
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )


@requires_db
async def test_skill_vectors_does_not_reuse_another_provenances_vectors(
    db_session: AsyncSession,
) -> None:
    """`skills_taxonomy` is GLOBAL and unscoped, so a recorded run (deterministic
    PSEUDO-vectors, no semantics) writes into the very rows live scoring reads. Reusing
    them silently collapsed every semantic cosine to noise on real data — the cache must
    only serve vectors from its own provenance."""
    skill = _unique_skill("python")
    await skill_vectors(
        db_session, {skill}, _deps_with(_CountingOpenAI(), pipeline_mode="recorded")
    )

    live = _CountingOpenAI()
    await skill_vectors(db_session, {skill}, _deps_with(live, pipeline_mode="live"))

    assert live.embedded == [[skill]], "recorded pseudo-vectors must never serve a live run"


@requires_db
async def test_skill_vectors_reembeds_when_the_embedding_model_changes(
    db_session: AsyncSession,
) -> None:
    """Vectors from a different embedding model live in a different space. Switching
    models must invalidate the cache, not silently compare across spaces."""
    skill = _unique_skill("python")
    await skill_vectors(
        db_session,
        {skill},
        _deps_with(_CountingOpenAI(), openai_embed_model="text-embedding-3-small"),
    )

    upgraded = _CountingOpenAI()
    await skill_vectors(
        db_session, {skill}, _deps_with(upgraded, openai_embed_model="text-embedding-3-large")
    )

    assert upgraded.embedded == [[skill]], "a model change must invalidate cached vectors"


@requires_db
async def test_skill_vectors_caching_preserves_curated_aliases(db_session: AsyncSession) -> None:
    """The cache writes through `skills_taxonomy`, which also carries hand-curated
    aliases. Filling in a vector must never clobber them."""
    canonical, alias = _unique_skill("python"), _unique_skill("py")
    db_session.add(SkillsTaxonomy(canonical=canonical, aliases=[alias]))
    await db_session.flush()

    await skill_vectors(db_session, {canonical}, _deps(_CountingOpenAI()))

    row = await db_session.scalar(
        select(SkillsTaxonomy).where(SkillsTaxonomy.canonical == canonical)
    )
    assert row is not None
    assert row.aliases == [alias]
    assert row.vec is not None


# --- ensure_candidate_vectors ---------------------------------------------------------


@requires_db
async def test_ensure_candidate_vectors_sets_when_null(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python", "PyTorch"])
    assert candidate.skills_vec is None

    await ensure_candidate_vectors(db_session, candidate, _deps(_EchoingOpenAI()))

    assert candidate.skills_vec is not None
    assert len(candidate.skills_vec) == 1536


@requires_db
async def test_ensure_candidate_vectors_noop_when_already_set(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python"])
    deps = _deps(_EchoingOpenAI())
    await ensure_candidate_vectors(db_session, candidate, deps)
    first_vec = candidate.skills_vec

    await ensure_candidate_vectors(db_session, candidate, deps)

    assert candidate.skills_vec == first_vec


@requires_db
async def test_ensure_candidate_vectors_noop_when_no_skills(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=[])

    await ensure_candidate_vectors(db_session, candidate, _deps(_EchoingOpenAI()))

    assert candidate.skills_vec is None


# --- score_posting ----------------------------------------------------------------


@requires_db
async def test_score_posting_computes_overlap_and_factors_in_range(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python", "PyTorch", "AWS"])
    targeting = await _make_targeting(
        db_session, user.id, role_titles=["ML Engineer"], seniority=["Senior"]
    )
    posting = await _make_posting(
        db_session,
        user.id,
        title="Senior ML Engineer",
        required_skills=["Python", "PyTorch", "Kubernetes"],
        seniority="Senior",
    )

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.overlap_matched == 2  # Python, PyTorch
    assert score.overlap_total == 3  # Python, PyTorch, Kubernetes
    assert 0 <= score.factor_role <= 100
    assert 0 <= score.factor_skill <= 100
    assert score.user_id == posting.user_id  # never from client input


@requires_db
async def test_score_posting_is_deterministic_across_runs(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python", "PyTorch"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=["Python", "PyTorch"]
    )
    deps = _deps(_EchoingOpenAI())
    await embed_posting(posting, deps)
    await ensure_candidate_vectors(db_session, candidate, deps)
    role_titles_vec = await _role_titles_vec(deps, targeting)
    mh_vecs = await _must_have_vecs(deps, targeting)

    first = await score_posting(
        db_session, user.id, posting, candidate, targeting, role_titles_vec, mh_vecs, deps
    )
    first_role, first_skill = first.factor_role, first.factor_skill

    second = await score_posting(
        db_session, user.id, posting, candidate, targeting, role_titles_vec, mh_vecs, deps
    )

    assert second.factor_role == first_role
    assert second.factor_skill == first_skill


@requires_db
async def test_score_posting_uses_taxonomy_aliases_for_overlap(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    # Unique canonical/alias per run — skills_taxonomy is a GLOBAL unscoped table (no
    # per-test RLS isolation from other committed data, e.g. the demo seeder), so a
    # fixed name like "python" could collide with a real row.
    canonical = f"kubernetes-{uuid4()}"
    alias = f"k8s-{uuid4()}"
    db_session.add(SkillsTaxonomy(canonical=canonical, aliases=[alias]))
    await db_session.flush()
    candidate = await _make_candidate(db_session, user.id, skills=[alias])  # alias, not canonical
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=[canonical]
    )

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.overlap_matched == 1
    assert score.overlap_total == 1


def _vec(*leading: float) -> list[float]:
    """A vector of the embedding column's width whose leading components are given."""
    return list(leading) + [0.0] * (1536 - len(leading))


class _PlantedVectorOpenAI(_EchoingOpenAI):
    """Returns planted vectors for named skills so a SEMANTIC match can be asserted
    deterministically. The recorded pseudo-vectors are random by construction, so they can
    only ever express identity — never 'PyTorch is near Machine Learning'."""

    def __init__(self, planted: dict[str, list[float]]) -> None:
        super().__init__()
        self._planted = planted

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        fallback = await super().embed(texts)
        return [
            self._planted.get(text, default) for text, default in zip(texts, fallback, strict=True)
        ]


@requires_db
async def test_score_posting_counts_a_semantically_covered_skill(
    db_session: AsyncSession,
) -> None:
    """The defect this whole change exists for: a required skill the candidate covers
    under a DIFFERENT name used to count as a miss."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    required_near, required_far = _unique_skill("machine-learning"), _unique_skill("rust")
    candidate_skill = _unique_skill("pytorch")
    openai = _PlantedVectorOpenAI(
        {
            required_near: _vec(1.0, 0.0, 0.0),
            candidate_skill: _vec(1.0, 1.0, 0.0),  # cos 0.707 -> covers "machine learning"
            required_far: _vec(0.0, 0.0, 1.0),  # orthogonal to the candidate -> a real miss
        }
    )
    candidate = await _make_candidate(db_session, user.id, skills=[candidate_skill])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session,
        user.id,
        title="ML Engineer",
        required_skills=[required_near, required_far],
    )

    score = await _score(db_session, user.id, posting, candidate, targeting, _deps(openai))

    assert score.overlap_matched == 1, "the near skill must count without an exact string match"
    assert score.overlap_total == 2, "the orthogonal skill must stay a miss"


@requires_db
async def test_score_posting_sets_red_flag_when_must_have_missing(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python"])
    targeting = await _make_targeting(
        db_session, user.id, role_titles=["ML Engineer"], must_haves=["Python", "Kubernetes"]
    )
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=["Python"]
    )

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.red_flag == "Missing must-have: Kubernetes"


@requires_db
async def test_score_posting_red_flag_none_when_all_must_haves_present(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python"])
    targeting = await _make_targeting(
        db_session, user.id, role_titles=["ML Engineer"], must_haves=["Python"]
    )
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=["Python", "Kubernetes"]
    )

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.red_flag is None


@requires_db
async def test_score_posting_never_sets_the_low_skill_read_model_flag(
    db_session: AsyncSession,
) -> None:
    """Near-zero skill overlap must NOT set red_flag here — services/jobs.py::score_match
    owns the '<45'-skill flag and cap at read time."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Excel"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session,
        user.id,
        title="ML Engineer",
        required_skills=["Python", "PyTorch", "Kubernetes", "Ray"],
    )

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.overlap_matched == 0
    assert score.red_flag is None


@requires_db
async def test_score_posting_is_salary_blind(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python", "PyTorch"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session,
        user.id,
        title="ML Engineer",
        required_skills=["Python", "PyTorch"],
        salary_text="$50k",
    )
    deps = _deps(_EchoingOpenAI())
    await embed_posting(posting, deps)
    await ensure_candidate_vectors(db_session, candidate, deps)
    role_titles_vec = await _role_titles_vec(deps, targeting)
    mh_vecs = await _must_have_vecs(deps, targeting)

    low = await score_posting(
        db_session, user.id, posting, candidate, targeting, role_titles_vec, mh_vecs, deps
    )
    low_factors = (low.factor_role, low.factor_skill, low.overlap_matched, low.overlap_total)

    posting.salary_text = "$500k"  # wildly different — must not move any factor
    high = await score_posting(
        db_session, user.id, posting, candidate, targeting, role_titles_vec, mh_vecs, deps
    )
    high_factors = (high.factor_role, high.factor_skill, high.overlap_matched, high.overlap_total)

    assert high_factors == low_factors


@requires_db
async def test_score_posting_rationale_is_generated_from_computed_factors(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python", "PyTorch"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=["Python", "PyTorch"]
    )
    openai = _EchoingOpenAI()

    score = await _score(db_session, user.id, posting, candidate, targeting, _deps(openai))

    assert score.rationale != ""
    assert openai.rationale_calls == [
        {
            "factors": {"role": score.factor_role, "skill": score.factor_skill},
            "overlap": (score.overlap_matched, score.overlap_total),
            "red_flag": score.red_flag,
        }
    ]
    assert score.rationale == (
        f"role={score.factor_role} skill={score.factor_skill} "
        f"overlap={score.overlap_matched}/{score.overlap_total} red_flag=none"
    )


@requires_db
async def test_score_posting_upsert_is_idempotent(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=["Python", "PyTorch"]
    )
    deps = _deps(_EchoingOpenAI())
    await embed_posting(posting, deps)
    await ensure_candidate_vectors(db_session, candidate, deps)
    role_titles_vec = await _role_titles_vec(deps, targeting)
    mh_vecs = await _must_have_vecs(deps, targeting)

    first = await score_posting(
        db_session, user.id, posting, candidate, targeting, role_titles_vec, mh_vecs, deps
    )
    assert first.overlap_matched == 1

    # Candidate profile changes -> re-scoring must UPDATE, not duplicate, the row.
    candidate.skills = ["Python", "PyTorch"]
    candidate.skills_vec = None
    await ensure_candidate_vectors(db_session, candidate, deps)
    updated = await score_posting(
        db_session, user.id, posting, candidate, targeting, role_titles_vec, mh_vecs, deps
    )

    rows = (await db_session.scalars(select(Score).where(Score.posting_id == posting.id))).all()
    assert len(rows) == 1
    assert rows[0].overlap_matched == updated.overlap_matched == 2


# --- ingest_company wiring (optional integration check) ---------------------------


class _FullStubOpenAI:
    """Hand-built OpenAIClient stub exercising the whole ingest_company pipeline:
    fixed enrich/extract results, deterministic pseudo-vector embeds (delegated to
    RecordedOpenAIClient), and a rationale that just echoes the computed factors."""

    def __init__(self, enrich_result: EnrichResult, extract_result: ExtractionResult) -> None:
        self._enrich_result = enrich_result
        self._extract_result = extract_result
        self._recorded = RecordedOpenAIClient(FIXTURES_DIR)

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        raise NotImplementedError

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        return self._enrich_result

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        return self._extract_result

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._recorded.embed(texts)

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
        raise NotImplementedError

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        return f"role={factors['role']} skill={factors['skill']}"

    async def aclose(self) -> None:
        return None


class _AnyDocFetcher:
    """Returns a fixed FetchedDoc for every URL requested."""

    def __init__(self, doc: FetchedDoc) -> None:
        self._doc = doc

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        return self._doc

    async def aclose(self) -> None:
        return None


@requires_db
async def test_ingest_company_scores_extracted_postings_for_read_model(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    db_session.add(CandidateProfile(user_id=user.id, skills=["Python", "PyTorch"]))
    db_session.add(
        Targeting(
            user_id=user.id,
            role_titles=["ML Engineer"],
            seniority=["Senior"],
            must_haves=["Python"],
        )
    )
    await db_session.flush()
    company_id = company.id

    shell = Posting(
        user_id=user.id,
        company_id=company.id,
        source="scrape",
        source_url="https://acme.com/jobs/1",
        content_hash="shell-1",
    )
    db_session.add(shell)
    await db_session.flush()
    posting_id = shell.id

    extract_result = ExtractionResult(
        title="Senior ML Engineer",
        required_skills=["Python", "PyTorch"],
        seniority="Senior",
        extraction_confidence=85,
    )
    openai = _FullStubOpenAI(EnrichResult(), extract_result)
    fetcher = _AnyDocFetcher(
        FetchedDoc(
            url="https://acme.com/jobs/1",
            status=200,
            text=_JOB_PAGE_TEXT,
        )
    )
    deps = PipelineDeps(
        openai=openai,
        fetcher=fetcher,
        settings=Settings(),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )

    await ingest_company(db_session, user.id, company_id, deps)

    score = await db_session.get(Score, posting_id)
    assert score is not None
    assert 0 <= score.factor_role <= 100
    assert 0 <= score.factor_skill <= 100
    assert score.rationale != ""

    job = await get_job(db_session, user.id, posting_id)
    assert job is not None
    assert 0 <= job.match <= 100
    assert job.rationale != ""


class _RejectsEmptyInputOpenAI(_FullStubOpenAI):
    """`_FullStubOpenAI` delegates embed to `RecordedOpenAIClient`, which loops over `texts`
    and so returns `[]` for `[]` without complaint. The LIVE client hands `input=` straight
    to the embeddings endpoint, which rejects an empty array — so the recorded client hides
    an empty-input bug rather than exposing it. This stub fails the way production does."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("embeddings input must not be empty (live API returns 400)")
        return await super().embed(texts)


@requires_db
async def test_ingest_company_does_not_embed_when_targeting_has_no_must_haves(
    db_session: AsyncSession,
) -> None:
    """`must_haves` defaults to `'{}'`, so empty is the normal state for a new user — not an
    edge case. Embedding it unconditionally sends an empty input to the live API and kills
    the whole run before a single posting is scored."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    db_session.add(CandidateProfile(user_id=user.id, skills=["Python"]))
    db_session.add(Targeting(user_id=user.id, role_titles=["ML Engineer"]))  # must_haves unset
    await db_session.flush()
    company_id = company.id

    shell = Posting(
        user_id=user.id,
        company_id=company.id,
        source="scrape",
        source_url="https://acme.com/jobs/1",
        content_hash="shell-empty-must-haves",
    )
    db_session.add(shell)
    await db_session.flush()
    posting_id = shell.id

    deps = PipelineDeps(
        openai=_RejectsEmptyInputOpenAI(
            EnrichResult(),
            ExtractionResult(
                title="Senior ML Engineer", required_skills=["Python"], extraction_confidence=85
            ),
        ),
        fetcher=_AnyDocFetcher(
            FetchedDoc(url="https://acme.com/jobs/1", status=200, text=_JOB_PAGE_TEXT)
        ),
        settings=Settings(),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )

    await ingest_company(db_session, user.id, company_id, deps)

    score = await db_session.get(Score, posting_id)
    assert score is not None, "the run must complete and score the posting"
    assert score.red_flag is None, "no must-haves means nothing can be missing"


# --- must-have coverage ---------------------------------------------------------------
#
# A must-have is a SKILL, matched against the posting's required skills — one register, one
# comparison. Measured on the live corpus that comparison is bimodal (70% at exactly 1.00,
# then a cliff to 0.48/0.33/0.23), which is what makes a threshold meaningful here.
#
# Criteria about the role as a whole ("Production ML or applied LLM work") are deliberately
# out of scope: that is an entailment question, and cosine measures topical similarity. It
# was tried against skill tokens, the aggregate skills vector, and the full
# title/summary/responsibilities text — every one produced a smooth ramp with no separating
# boundary. Those belong in `targeting.preferences`, which does not drive scoring.


@requires_db
async def test_score_posting_covers_a_must_have_named_differently(
    db_session: AsyncSession,
) -> None:
    """The must-have is compared as an embedding, so it need not be worded identically to
    the posting's skill — exact string matching flagged 53 of 53 postings in the corpus."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    must_have, near_skill = _unique_skill("python"), _unique_skill("python3")
    openai = _PlantedVectorOpenAI(
        {
            must_have: _vec(1.0, 0.0),
            near_skill: _vec(1.0, 0.2),  # cos 0.98 -> covered
        }
    )
    candidate = await _make_candidate(db_session, user.id, skills=[near_skill])
    targeting = await _make_targeting(
        db_session, user.id, role_titles=["ML Engineer"], must_haves=[must_have]
    )
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=[near_skill]
    )

    score = await _score(db_session, user.id, posting, candidate, targeting, _deps(openai))

    assert score.red_flag is None


@requires_db
async def test_score_posting_flags_a_must_have_no_skill_covers(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    must_have, unrelated = _unique_skill("python"), _unique_skill("welding")
    openai = _PlantedVectorOpenAI(
        {
            must_have: _vec(1.0, 0.0),
            unrelated: _vec(0.0, 1.0),  # orthogonal -> genuinely absent
        }
    )
    candidate = await _make_candidate(db_session, user.id, skills=[unrelated])
    targeting = await _make_targeting(
        db_session, user.id, role_titles=["ML Engineer"], must_haves=[must_have]
    )
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=[unrelated]
    )

    score = await _score(db_session, user.id, posting, candidate, targeting, _deps(openai))

    assert score.red_flag == f"Missing must-have: {must_have}"


@requires_db
async def test_score_posting_no_must_haves_means_no_red_flag(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["ML Engineer"])
    posting = await _make_posting(
        db_session, user.id, title="ML Engineer", required_skills=["Python"]
    )

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.red_flag is None


@requires_db
async def test_score_posting_flags_a_must_have_when_posting_lists_no_skills(
    db_session: AsyncSession,
) -> None:
    """Nothing to compare against is not coverage — an unextractable posting must not
    silently satisfy every must-have."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    candidate = await _make_candidate(db_session, user.id, skills=["Python"])
    targeting = await _make_targeting(
        db_session, user.id, role_titles=["ML Engineer"], must_haves=["Python"]
    )
    posting = await _make_posting(db_session, user.id, title="ML Engineer", required_skills=[])

    score = await _score(
        db_session, user.id, posting, candidate, targeting, _deps(_EchoingOpenAI())
    )

    assert score.red_flag == "Missing must-have: Python"


# --- rescore_all --------------------------------------------------------------------


async def _make_scorable_posting(
    session: AsyncSession, user_id: UUID, company_id: UUID, deps: PipelineDeps, *, title: str
) -> Posting:
    posting = Posting(
        user_id=user_id,
        company_id=company_id,
        source="scrape",
        source_url=f"https://acme.com/jobs/{uuid4()}",
        content_hash=f"hash-{uuid4()}",
        title=title,
        required_skills=["Python", "SQL"],
        extraction_confidence=90,
    )
    session.add(posting)
    await session.flush()
    await embed_posting(posting, deps)
    return posting


@requires_db
async def test_rescore_all_rescored_scores_reflect_the_current_profile(
    db_session: AsyncSession,
) -> None:
    """Editing the profile then re-scoring updates the stored Score against the NEW targeting —
    the whole point of the feature — and upserts (no duplicate Score rows)."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    deps = _deps(_EchoingOpenAI())

    await _make_candidate(db_session, user.id, skills=["Python", "SQL"])
    targeting = await _make_targeting(db_session, user.id, role_titles=["Data Scientist"])
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()
    posting = await _make_scorable_posting(
        db_session, user.id, company.id, deps, title="Data Scientist"
    )

    assert await rescore_all(db_session, user.id, deps) == 1
    before = await db_session.get(Score, posting.id)
    assert before is not None
    role_before = before.factor_role

    # Change the profile to an unrelated role, then re-score.
    targeting.role_titles = ["Veterinary Nurse"]
    await db_session.flush()
    assert await rescore_all(db_session, user.id, deps) == 1  # same posting, re-scored

    after = await db_session.get(Score, posting.id)
    assert after is not None
    assert after.factor_role != role_before  # score now reflects the new profile
    # Idempotent upsert: still exactly one Score row for the posting.
    count = await db_session.scalar(
        select(func.count()).select_from(Score).where(Score.user_id == user.id)
    )
    assert count == 1


@requires_db
async def test_rescore_all_skips_opted_out_companies(db_session: AsyncSession) -> None:
    """A removed (opted-out) company's postings must not be re-scored."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    deps = _deps(_EchoingOpenAI())

    await _make_candidate(db_session, user.id, skills=["Python"])
    await _make_targeting(db_session, user.id, role_titles=["Data Scientist"])
    kept = Company(user_id=user.id, name="Kept", domain="kept.example")
    removed = Company(user_id=user.id, name="Removed", domain="removed.example", opt_out=True)
    db_session.add_all([kept, removed])
    await db_session.flush()
    await _make_scorable_posting(db_session, user.id, kept.id, deps, title="Data Scientist")
    await _make_scorable_posting(db_session, user.id, removed.id, deps, title="Data Scientist")

    assert await rescore_all(db_session, user.id, deps) == 1  # only the kept company's posting


@requires_db
async def test_latest_run_excludes_rescore_runs(db_session: AsyncSession) -> None:
    """The sidebar's 'synced' line is about discovery, so a later rescore run must not supersede
    the last discovery run as `latest_run`."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)

    discovery = await create_run(db_session, user.id, kind="on_demand")
    await create_run(db_session, user.id, kind="rescore")  # more recent, but not a discovery

    latest = await latest_run(db_session, user.id)
    assert latest is not None
    assert latest.id == discovery.id
    assert latest.kind != "rescore"

    # Sanity: the rescore run does exist in the table, just excluded from latest_run.
    all_kinds = set(await db_session.scalars(select(Run.kind).where(Run.user_id == user.id)))
    assert all_kinds == {"on_demand", "rescore"}
