from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Approval, Company, Posting, User
from specula_api.db.session import async_session
from specula_api.pipeline.deps import DEFAULT_FIXTURES_DIR, build_recorded_deps
from specula_api.pipeline.openai_client import (
    EnrichResult,
    ExtractionResult,
    RecordedOpenAIClient,
    Source,
)
from specula_api.seed import DEMO_GOOGLE_SUB, seed
from specula_api.services.approval import apply_decision
from specula_api.services.run import create_run, ingest_company, latest_run

_FROZEN_NOW = datetime(2026, 7, 5, tzinfo=UTC)
_NEW_COMPANY_DOMAIN = "acme.com"  # not one of the seeder's own _COMPANIES domains


class _RecordedExceptRationale:
    """Wraps `RecordedOpenAIClient`, replacing only `rationale` with a deterministic echo of
    its inputs. `rationale`'s factors are COMPUTED from embeddings (pipeline/score.py) and
    this test doesn't control their exact values, so no fixed fixture key could match them —
    every other call goes through the real recorded fixtures (mirrors tests/test_score.py's
    `_EchoingOpenAI`)."""

    def __init__(self, fixtures_dir: object) -> None:
        self._recorded = RecordedOpenAIClient(fixtures_dir)  # type: ignore[arg-type]

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        return await self._recorded.discover_sources(queries, allowed_domains=allowed_domains)

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        return await self._recorded.enrich_company(name=name, domain=domain, page_text=page_text)

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        return await self._recorded.extract_posting(page_text=page_text, company_name=company_name)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._recorded.embed(texts)

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        return f"role={factors['role']} skill={factors['skill']} overlap={overlap[0]}/{overlap[1]}"

    async def aclose(self) -> None:
        return None


@requires_db
async def test_seed_is_idempotent_and_seeds_low_confidence_posting() -> None:
    # Run twice; the demo user and its row counts must be stable (no duplication).
    async with async_session() as session:
        await seed(session)
        await session.commit()
    async with async_session() as session:
        await seed(session)
        await session.commit()

    async with async_session() as session:
        demo_users = (
            await session.scalars(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
        ).all()
        assert len(demo_users) == 1
        uid = demo_users[0].id

        # Tenant context needed to read the FORCE-RLS'd postings.
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(uid))
        )
        posting_count = await session.scalar(select(func.count()).select_from(Posting))
        assert posting_count == 13  # stable across the two seed runs

        min_conf = await session.scalar(select(func.min(Posting.extraction_confidence)))
        assert min_conf is not None  # the low-confidence posting exists
        assert min_conf < 50


@requires_db
async def test_recorded_ingest_is_additive_over_seeded_demo_data() -> None:
    """The demo seeder and a real (recorded-deps) `ingest_company` call must coexist:
    approving + ingesting a NEW company under the demo user adds rows without violating
    `unique(user_id, content_hash)` / `unique(user_id, domain)`, leaves every already-seeded
    row untouched, and doesn't disturb the seeder's own `Run` row until a later run
    supersedes it."""
    async with async_session() as session:
        await seed(session)
        await session.commit()

    async with async_session() as session:
        demo_user = await session.scalar(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
        assert demo_user is not None
        uid = demo_user.id
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(uid))
        )

        seeded_run = await latest_run(session, uid)
        assert seeded_run is not None
        assert seeded_run.kind == "scheduled"  # the seeder's own Run, not a fresh one

        seeded_company_domains = set(
            await session.scalars(select(Company.domain).where(Company.user_id == uid))
        )
        assert _NEW_COMPANY_DOMAIN not in seeded_company_domains
        seeded_content_hashes = set(
            await session.scalars(select(Posting.content_hash).where(Posting.user_id == uid))
        )

        approval = Approval(
            user_id=uid, name="Acme Corp", domain=_NEW_COMPANY_DOMAIN, ats="greenhouse"
        )
        session.add(approval)
        await session.flush()

        result = await apply_decision(session, uid, approval.id, "approve")
        assert result is not None
        _decided, company_id = result
        assert company_id is not None

        deps = replace(
            build_recorded_deps(Settings(), DEFAULT_FIXTURES_DIR, now=_FROZEN_NOW),
            openai=_RecordedExceptRationale(DEFAULT_FIXTURES_DIR),
        )
        await ingest_company(session, uid, company_id, deps)

        # Additive, not destructive: every seeded company/posting is still there...
        companies_after = (
            await session.scalars(select(Company).where(Company.user_id == uid))
        ).all()
        postings_after = (
            await session.scalars(select(Posting).where(Posting.user_id == uid))
        ).all()
        assert seeded_company_domains <= {c.domain for c in companies_after if c.domain}
        assert len(companies_after) == len(seeded_company_domains) + 1

        # ...and the new company's postings are genuinely new rows (no unique-constraint clash).
        new_postings = [p for p in postings_after if p.company_id == company_id]
        assert new_postings
        assert {p.content_hash for p in new_postings}.isdisjoint(seeded_content_hashes)
        assert len(postings_after) == len(seeded_content_hashes) + len(new_postings)

        # The demo persona targets Data Scientist / ML roles, so fetch.py's relevance gate
        # keeps the board's "Staff Data Scientist" and drops its backend/PM postings.
        extracted = next(p for p in new_postings if p.title == "Staff Data Scientist")
        assert extracted.required_skills  # a real extraction, not a placeholder

        # The seeder's own Run row is untouched — ingest_company never writes to `runs`.
        still_latest = await latest_run(session, uid)
        assert still_latest is not None
        assert still_latest.id == seeded_run.id

        await session.commit()

    # A later run supersedes the seeder's Run as `latest_run`.
    async with async_session() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(uid))
        )
        new_run = await create_run(session, uid)
        await session.commit()

    async with async_session() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(uid))
        )
        current_latest = await latest_run(session, uid)
        assert current_latest is not None
        assert current_latest.id == new_run.id
