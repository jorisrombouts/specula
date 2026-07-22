# M4 — Extraction & scoring · STATUS: ✅ COMPLETE (merged PRs #3–#13, `45dee7f`)

> Core M4 landed in PRs #3–#9 (`fb9d0a0`). Scoring/extraction quality then continued in
> PRs #10–#13 — recorded below under "Scoring-quality follow-ups." M5 (Hardening) has not
> started: observability, rate limits, export/delete and load testing are all untouched.

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
- **CI:** green on every merge. **388 tests passing** (356 at core-M4 close, +32 from the
  scoring-quality follow-ups), ruff + mypy `--strict` clean.

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

## Scoring-quality follow-ups (PRs #10–#13)

After the pre-M5 audit, running the pipeline over a wider live corpus (4 → 54 postings) exposed
that scoring was systematically *understating* matches. Four PRs fixed it end to end:

| PR | Change | Why it mattered |
|---|---|---|
| #10 | Ground the dedup 0.92 threshold in recorded embeddings; record M4 status; add `just db-reset` | The threshold had never been checked against a real embedding; a code comment claimed a seniority pair "embeds near-identically" when the recorded pair sits at 0.68 |
| #11 | Score skills by **embedding similarity**, not string equality | A candidate with PyTorch scored **zero** against "Machine Learning"; every posting collapsed onto Python+SQL and tripped the low-overlap red flag |
| #12 | Extract **atomic skill names**, not requirement prose; match must-haves as skills | 11% of extracted "skills" were sentences that embed nowhere near a skill token — the same understatement, one stage upstream and immune to any threshold |
| #13 | Stop applying the skill-token guard to `nice_to_have` | That field is display-only (never embedded/scored); the guard was discarding readable prose the reader would otherwise see |

Two bugs were caught in review and fixed before merge, both invisible to the test suite because
`RecordedOpenAIClient` masks them: an **empty `must_haves`** list (the default for a new user) would
send an empty input to the live embeddings API and kill the run; and a provenance guard (`vec_model`)
was added so a recorded/test run's pseudo-vectors can't poison the global `skills_taxonomy` cache that
live scoring reads. See `docs/SKILL-MATCHING.md` for the threshold derivation.

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
- **Recorded fixtures are a curated set, not an archive.** 117 committed OpenAI shapes; the ~106
  additional captures from the 2026-07-21 live runs were cleared after confirming the suite stays
  green without them. Re-recording costs OpenAI credits. `fixtures/pipeline/http/*.json` is
  gitignored by design.
- **A record-mode run can clobber a hand-authored fixture.** One overwrote `enrich/lighthouse.app.json`
  with a live US response, producing local-only failures that were *not* real regressions. Record
  mode writes by key and does not ask.
- Carried from M3: the visual-harness clock pin reaches the browser but not SSR, and favicon `<img>`s
  render as alt-text in visual baselines. Both cosmetic, both tolerated.

### Open, from the PR #10–#13 reviews (none blocking)

- **`just db-bootstrap` fails from inside a git worktree.** It uses `docker compose exec`, which
  scopes the project by directory name, so from a worktree it can't see the running `postgres`
  container. The recipe was written for per-worktree DBs — exactly the case that breaks. Workaround:
  `docker exec specula-postgres-1 …` directly.
- **Must-haves bypass the taxonomy alias map.** `required_skills` resolve through `_canonicalize`
  before embedding; must-haves are only casefolded. Given an alias row the two sides embed as near
  neighbours rather than at exactly 1.0 — survives the threshold in practice, worth unifying.
- **The 54-posting live corpus figures aren't reproducible from committed artifacts** — no fixture
  encodes them, and `nice_to_have`/skill-shape claims came from a manual live run. A debug log of
  guard-dropped entries would make it continuously verifiable.
