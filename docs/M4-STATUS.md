# M4 — Extraction & scoring · STATUS: ✅ COMPLETE (merged PRs #3–#9, `fb9d0a0`)

**What shipped:** M3 delivered the pipeline; M4 is where it was **pointed at the real internet and
made to survive it**. Everything below was found by running

`discover (OpenAI web-search) → approval queue → approve → enrich → crawl ATS/careers → extract
(LLM structured output) → embed → dedup → salary-blind scoring + rationale → write`

against live ATS boards with a real API key — not by reading the code. Up to this point the whole
pipeline had only ever executed against recorded fixtures.

- **ATS coverage 3 → 6** adapters (added Recruitee, Workable, Personio). **SmartRecruiters was
  dropped deliberately** — its `robots.txt` disallows us.
- **Execution stays inline** (FastAPI `BackgroundTask` + `tenant_session`); still no Redis / Arq /
  worker / always-on host. `RUN_LIVE_SMOKE=1` and `PIPELINE_MODE=record` remain the "prove the
  product" gates — see `docs/RUNNING-LIVE.md`.
- **CI:** green on every one of the seven merges. **356 tests passing**, ruff + mypy `--strict` clean.

## What live running exposed

Nine bugs in the first pass (PR #3), every one invisible to the fixture suite:

| # | Bug | Consequence |
|---|---|---|
| 1 | discovery omitted `include=[web_search_call.action.sources]` | found nothing, **silently** |
| 2 | raw HTML passed to the LLM | context overflow |
| 3 | noisy seed queries | 0 companies where 20+ were available |
| 4 | DNS / dead-host crash | one bad domain killed the run |
| 5 | no per-company extraction cap | a 662-job board → 600+ LLM calls |
| 6 | no role gate on extraction | sales roles extracted against an ML profile |
| 7 | blank `PIPELINE_MODE=` | crash |
| 8 | role gate narrowed the lifecycle set | narrowing role titles retired live postings |
| 9 | adapters returned `[]` on an unreadable board | read as "board empty" → **retired the company's whole pool** |

Then crawler hardening (PRs #4, #5): an SSRF guard refusing non-public fetch targets, a bounded
`Retry-After`, host-verified board tokens, a tighter generic scrape, and a stop on claiming other
companies' postings. Plus a test-user sweep — auth-provisioned users were leaking across the suite.

## The pre-M5 audit

Before starting M5 the codebase was audited for anything that would silently degrade data quality
once more was built on top. Five issues, all closed, plus a sixth the live runs turned up:

| # | Issue | Landed |
|---|---|---|
| 1 | Discovery discarded the real careers URL — enrichment then ran blind against a *fabricated* domain and paid an LLM to guess the URL back | PR #6 |
| 2 | `GenericHtmlAdapter` still had the mass-close bug: `return []` where it meant `BoardUnavailable` | PR #6 |
| 3 | Dedup was a stub — cross-source clustering was `TODO`, and `dedup_group` was consumed by **nobody**. The spec's "pool is deduped on read" had never actually been built | PR #7 |
| 4 | Approval "why" was an f-string template, brushing the invariant *numbers computed, prose LLM-generated — never the reverse* | PR #8 |
| 5 | Personio adapter always built a `.de` URL, sending `.com` companies to a host that wasn't theirs; a bare `jobs.personio.de` yielded the token `"jobs"` | PR #8 |
| 6 | **Found live:** extraction emits `"Spain"`, every consumer expects `"ES"` — so location-scoped lenses matched *only* seeded rows, and the foreign-HQ scoring rule compared `'Spain' != 'ES'` and was wrong in both directions | PR #9 |

## Latent bugs found en route

1. **Enrichment overwrote the discovered `careers_url` with the model's guess.** Surfaced only by
   fix #1's test — it would have silently undone that fix on the second run of every company.
2. **Alembic autogenerate wants to drop two indexes on every run.** `ix_approvals_user_id_undecided`
   (partial) and `ix_postings_skills_vec` (ivfflat) are created by M2 via raw `op.execute` and aren't
   declared on the models. The migration is hand-trimmed with a note; autogenerate output must be
   read, not trusted.
3. **Dedup clustering deviates from the spec, deliberately.** Clustering is scoped *within* a company
   and carries a seniority guard. Measured `pg_trgm`: "Data Scientist" vs "Senior Data Scientist"
   matches at 0.71 — the spec's threshold alone would have merged two distinct openings.

## Deferred to the automation milestone (documented, not built)

Weekly per-user scheduler (staggered) · Arq worker + Upstash Redis + always-on host (hosting decision
still open) · on-demand rate-limit gate · Playwright/JS-rendered source adapter · SSE `/runs/stream` ·
feedback-signal weight nudging.

## Known follow-ups (non-blocking)

- **The 0.92 cosine threshold is only partially grounded.** Recorded embeddings now pin that the
  three real titles whose source text is recoverable all sit below it (`test_dedup.py`), and that
  seniority variants land near 0.68 rather than "near-identical" as previously claimed. Three titles
  is not a threshold study — properly characterising 0.92 needs a live embedding run over many real
  title pairs.
- **Recorded fixtures are a curated set, not an archive.** 119 committed OpenAI shapes; the ~106
  additional captures from the 2026-07-21 live runs were cleared after confirming the suite stays
  green without them. Re-recording costs OpenAI credits. `fixtures/pipeline/http/*.json` is
  gitignored by design.
- **A record-mode run can clobber a hand-authored fixture.** One overwrote `enrich/lighthouse.app.json`
  with a live US response, producing local-only failures that were *not* real regressions. Record
  mode writes by key and does not ask.
- Carried from M3: the visual-harness clock pin reaches the browser but not SSR, and favicon `<img>`s
  render as alt-text in visual baselines. Both cosmetic, both tolerated.
