"""Live/record pipeline harness: `python -m specula_api.cli <discover|ingest|prove-live>`.

Runs the real discovery/enrich/crawl/extract/embed/score pipeline against the demo tenant
(`seed.py::DEMO_GOOGLE_SUB`) on the configured DB, via `tenant_session` + `build_deps(settings)`
exactly like `tests/test_live_smoke.py`. This is the "one command" harness the owner runs with a
real `OPENAI_API_KEY` to prove the live path and regenerate recorded fixtures — see
`docs/RUNNING-LIVE.md`. Not imported by the app or the test suite.
"""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select

from specula_api.config import settings
from specula_api.db.models import Approval, Posting, Score, User
from specula_api.db.session import async_session, tenant_session
from specula_api.pipeline.deps import PipelineDeps, build_deps
from specula_api.seed import DEMO_GOOGLE_SUB
from specula_api.services.approval import apply_decision
from specula_api.services.run import create_run, ingest_company, run_discovery


def _require_api_key() -> None:
    if not settings.openai_api_key:
        raise SystemExit(
            "OPENAI_API_KEY is not set. Export it before running the live pipeline, e.g.:\n"
            "  OPENAI_API_KEY=sk-... PIPELINE_MODE=record just prove-live"
        )


async def _demo_user_id() -> UUID:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
    if user is None:
        raise SystemExit("Demo user not found — run `just seed` first.")
    return user.id


def _print_postings(postings: list[Posting], scores: dict[UUID, Score | None]) -> None:
    if not postings:
        print("  (no postings extracted)")
        return
    for posting in postings:
        score = scores.get(posting.id)
        title = posting.title or f"(unextracted) {posting.source_url}"
        if score is None:
            print(f"  - {title} — unscored")
        else:
            print(
                f"  - {title} — role={score.factor_role} skill={score.factor_skill} "
                f"overlap={score.overlap_matched}/{score.overlap_total}"
            )
            print(f"      {score.rationale}")


async def cmd_discover() -> None:
    _require_api_key()
    user_id = await _demo_user_id()
    deps: PipelineDeps = build_deps(settings)
    try:
        async with tenant_session(user_id) as session:
            run = await create_run(session, user_id)
            await run_discovery(session, user_id, run.id, deps)
            approvals = list(
                (
                    await session.scalars(
                        select(Approval)
                        .where(Approval.user_id == user_id, Approval.decision.is_(None))
                        .order_by(Approval.created_at)
                    )
                ).all()
            )
    finally:
        await deps.aclose()

    print(f"Run {run.id} [{run.status}]: {run.stats}")
    print(f"{len(approvals)} undecided approval(s):")
    for approval in approvals:
        print(f"  - [{approval.ats or 'no ATS detected'}] {approval.name} — {approval.domain}")


async def cmd_ingest(domain: str) -> None:
    _require_api_key()
    user_id = await _demo_user_id()
    deps = build_deps(settings)
    try:
        async with tenant_session(user_id) as session:
            approval = await session.scalar(
                select(Approval).where(
                    Approval.user_id == user_id,
                    Approval.decision.is_(None),
                    Approval.domain == domain,
                )
            )
            if approval is None:
                raise SystemExit(
                    f"No undecided approval with domain {domain!r}. Run `just live-discover` "
                    "first, or check the domain against its output."
                )

            decided = await apply_decision(session, user_id, approval.id, "approve")
            assert decided is not None
            _approval, company_id = decided
            if company_id is None:
                raise SystemExit(f"Approving {domain!r} did not resolve to a company.")

            await ingest_company(session, user_id, company_id, deps)

            postings = list(
                (
                    await session.scalars(
                        select(Posting).where(
                            Posting.user_id == user_id, Posting.company_id == company_id
                        )
                    )
                ).all()
            )
            scores = {posting.id: await session.get(Score, posting.id) for posting in postings}
    finally:
        await deps.aclose()

    print(f"Ingested {domain}: {len(postings)} posting(s)")
    _print_postings(postings, scores)


async def cmd_prove_live() -> None:
    _require_api_key()
    user_id = await _demo_user_id()
    deps = build_deps(settings)
    try:
        async with tenant_session(user_id) as session:
            run = await create_run(session, user_id)
            await run_discovery(session, user_id, run.id, deps)
            print(f"Discovery run {run.id} [{run.status}]: {run.stats}")

            # ONE company only — cost guardrail (discovery is already capped at
            # settings.discovery_max_searches queries; ingest doesn't fan out further).
            approval = await session.scalar(
                select(Approval)
                .where(
                    Approval.user_id == user_id,
                    Approval.decision.is_(None),
                    Approval.ats.is_not(None),
                )
                .order_by(Approval.created_at)
            )
            if approval is None:
                raise SystemExit("Discovery found no ATS-detected approvals — nothing to ingest.")

            print(f"Ingesting first ATS-detected approval: {approval.name} ({approval.domain})")
            decided = await apply_decision(session, user_id, approval.id, "approve")
            assert decided is not None
            _approval, company_id = decided
            assert company_id is not None

            await ingest_company(session, user_id, company_id, deps)

            postings = list(
                (
                    await session.scalars(
                        select(Posting).where(
                            Posting.user_id == user_id, Posting.company_id == company_id
                        )
                    )
                ).all()
            )
            scores = {posting.id: await session.get(Score, posting.id) for posting in postings}
    finally:
        await deps.aclose()

    print(f"Scored postings for {approval.domain}:")
    _print_postings(postings, scores)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m specula_api.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("discover", help="run discovery for the demo user")
    ingest_parser = subparsers.add_parser("ingest", help="approve + ingest one domain")
    ingest_parser.add_argument("domain", help="domain of the undecided approval to ingest")
    subparsers.add_parser("prove-live", help="discover, ingest one company, print scored jobs")
    args = parser.parse_args()

    if args.command == "discover":
        asyncio.run(cmd_discover())
    elif args.command == "ingest":
        asyncio.run(cmd_ingest(args.domain))
    elif args.command == "prove-live":
        asyncio.run(cmd_prove_live())


if __name__ == "__main__":
    main()
