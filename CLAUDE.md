# Specula — project guide for Claude

Personal, multi-tenant "role ledger": job discovery + salary-blind match scoring, editorial-
instrument UI. Built in phases (M0–M6) from a Claude Design prototype.

## Source of truth (read before building)
- `docs/Specula - Design Spec.md` — architecture, data model, behavior, milestones (authoritative).
- `docs/Specula - Design Spec (prototype).md` + `prototype/` — pixel-faithful UI to port 1:1.
- Re-sync from Claude Design project `0d5106d9-4ebd-46fd-957b-b1e7bcdf3bff` (`/design-login` + DesignSync).
- Conflict rule: visuals → prototype wins; architecture/behavior → spec wins.

## Deliberate deviations from the spec (DO NOT re-add by following the spec verbatim)
- NO billing / Stripe / paid plan tiers / entitlement gating. Specula is free to use.
- NO object storage. Keep `content_hash` + `source_url`; logos via favicon URL.

## How we build
- One phase at a time via superpowers: brainstorm → writing-plans → executing-plans; TDD for logic;
  verification-before-completion before any "done"; code-review before merge.
- Default to YAGNI/KISS: no service, file, folder, or abstraction until the milestone that needs it.

## Stack & hosting (free-tier first)
- Monorepo: `apps/api` (FastAPI · uv · ruff · mypy --strict · pytest) + `apps/web` (Next 15 · TS strict
  · Tailwind · ESLint + Prettier). pnpm workspace + `packages/shared-types` arrive in M1.
- Vercel (web) + Neon (Postgres+pgvector) + Upstash (Redis, M3). OpenAI is the only paid piece. Avoid paid infra.

## Product invariants (central, easy to break)
- Counts are DERIVED server-side, never stored/hard-coded.
- Salary NEVER ranks or filters; shown only when stated. Scoring is salary-blind.
- Scores: numbers computed (deterministic/embeddings), prose LLM-generated — never the reverse.
- Low-confidence extractions are "surfaced, not trusted" and excluded from Insights.
