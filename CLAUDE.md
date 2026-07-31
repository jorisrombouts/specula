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
- Next.js **16** (not the spec's "15"). Override approved 2026-06-30 (Phase 0): `create-next-app@latest`
  ships 16; it builds/lints/type-checks clean. Future phases target 16. Note: Next 16 uses Turbopack
  for production builds by default.
- **M6 is scoped DOWN from spec §18** (owner decision 2026-07-31). Dropped outright:
  **keyboard-nav/a11y** (so spec §14's "Tab/arrow nav in the Jobs list" + focus-states pass is
  NOT a deliverable) and the **perf budget**. M6 is onboarding + empty/loading states + security
  review, nothing else. The motion rules already shipped (`prefers-reduced-motion`, Esc-closes-
  drawer) stay as-is — they are done, not scope.

## How we build
- One phase at a time via superpowers: brainstorm → writing-plans → executing-plans; TDD for logic;
  verification-before-completion before any "done"; code-review before merge.
- Default to YAGNI/KISS: no service, file, folder, or abstraction until the milestone that needs it.
- **Done (M0–M5):** the full pipeline discovery→approval→crawl→extract→score runs on a **manual
  trigger, inline** — scheduler/worker/hosting deferred. M4 is live-proven against real ATS boards
  and real OpenAI calls; M5 hardened it (observability + OpenAI token usage ledger (no spend
  cap), rate limits, GDPR export/delete + per-company opt-out, run & token dashboard, k6 load
  + E2E). See `docs/M5-STATUS.md` (+ `docs/M4-STATUS.md`).
- **Current focus (M6 — Polish & launch):** onboarding (collect starting companies),
  empty/loading states, security review. That is the whole list — keyboard-nav/a11y and the
  perf budget were cut (see deviations above). *(Spec §18, scoped down.)*
- **Parallel track:** the remaining **M5 follow-ups** (GDPR export breadth is the substantive
  one) are being done in a SEPARATE worktree, not here. Don't pick them up in an M6 session —
  you'll collide. See `docs/M5-STATUS.md` for the list.

## Stack & hosting (free-tier first)
- Vercel (web) + Neon (Postgres+pgvector) + Upstash (Redis) — deferred with the scheduler (later
  milestone); the manual pipeline runs inline. OpenAI is the only paid piece. Avoid paid infra.
- Auth: Auth.js v5 (NextAuth), **Google-only** sign-in, **JWT (stateless) session** — no DB adapter;
  FastAPI owns the DB. Dev DB = local docker Postgres (`just up`); Neon is a deploy-time DATABASE_URL swap.
  DB access is async SQLAlchemy 2.0 + Alembic (first migration = `users`, identity only).

## Product invariants (central, easy to break)
- Counts are DERIVED server-side, never stored/hard-coded.
- Salary NEVER ranks or filters; shown only when stated. Scoring is salary-blind.
- Scores: numbers computed (deterministic/embeddings), prose LLM-generated — never the reverse.
- Low-confidence extractions are "surfaced, not trusted" and excluded from Insights.
