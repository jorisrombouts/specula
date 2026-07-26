# Cheaper, controllable discovery — design

**Goal:** Cut the cost and time of a discovery run (currently ~$0.33 and ~85s,
dominated by ~12–17 OpenAI web-search calls) without meaningfully losing company
coverage, and give the user a UI control over the search ceiling.

## Motivation (measured)

From the live cost ledger, a discovery run does **~12–17 web-search calls** at
**~$0.024 each** (the web-search *tool fee* dominates, not tokens). Two wastes:

1. **Synonym role titles.** `build_seed_queries` emits one search per role title
   × per active lens. A user with 6 near-synonym titles
   (`Machine Learning Engineer`, `ML Engineer`, `Data Scientist`,
   `Senior Data Scientist`, `AI Engineer`, `AI Developer`) × 2 lenses = ~12
   heavily-overlapping searches.
2. **Re-discovering known companies.** ~80% of what a run finds is already known
   (`found: ~50, new: ~10`) and gets deduped — but the searches still cost money
   every run.

The cost is **per search, not per result** — discovery already skips known
companies for free (dedup runs before any LLM description call). So savings come
from **running fewer searches**, not from processing results differently.

## The four changes

### 1. Synonym collapse — one combined role search per lens

`build_seed_queries` changes from "one query per role title per lens" to **one
combined role query per active lens**, joining the role titles into a single
search string (e.g. `machine learning engineer / data scientist / ai engineer
jobs Spain`). Lens **seeds still run first, verbatim** (user-crafted, high-signal).

- Effect: ~12 role searches → **1 per active lens** (~2 for a 2-lens user).
- The role titles list is unchanged — it still feeds the role-match scoring
  factor. Only how it maps to *searches* changes.
- **Fallback** (decided by the live A/B in Validation): if a single combined
  query dilutes results, cap distinct role searches at 2–3 instead of combining
  all.

### 2. Cheaper discovery model — gpt-4o-mini

Discovery only harvests source URLs; it does not need `gpt-4o`. Add a dedicated
`openai_discovery_model` setting defaulting to **`gpt-4o-mini`** and use it for
`discover_sources`. `openai_search_model` is left as-is for any other caller.

### 3. Smart cache — query-exhaustion memory

A query that keeps re-finding only already-known companies is "exhausted" and
should be parked. New per-user, per-query memory records this and skips exhausted
queries on future runs, retrying them after a cooldown (new postings appear over
time).

**Data:** new table `discovery_query_stat`:

| column | type | notes |
|---|---|---|
| `user_id` | uuid | FK, part of PK, RLS-scoped |
| `query` | text | the exact search string, part of PK |
| `last_run_at` | timestamptz | when this query last executed |
| `consecutive_empty_runs` | int | runs in a row that found 0 new companies |

**Skip rule (before a run):** a candidate query is skipped when
`consecutive_empty_runs >= 2` **AND** `last_run_at` is within the last **7 days**.
Past 7 days it runs again (one retry); if it's still empty the cooldown re-arms.

**Update rule (after a run):** for each query that actually executed, upsert its
stat — `last_run_at = now`; if it found ≥1 new company, reset
`consecutive_empty_runs = 0`, else increment it.

**Scope of exhaustion:** applies to the **auto-generated combined-role queries
only**. User-written lens **seeds always run** (explicit intent is respected).
This matches the behavior described to the user; parking seeds too is a possible
later extension.

### 4. UI-controllable max searches

- The global default `discovery_max_searches` drops from **20 → 10**.
- Add a nullable `discovery_max_searches` column to the existing **`UserSettings`**
  table (`user_id` PK, already holds visual `tweaks`). `NULL` → use the global
  default. Valid range **1–20**.
- `discover()` reads the user's value (via a small service helper), falling back
  to the global default.
- **API:** a small dedicated endpoint pair, e.g. `GET /api/v1/settings/discovery`
  → `{ maxSearches: number }` and `PUT` to update it (validated 1–20). Kept
  separate from the visual `tweaks` payload, which is unrelated.
- **UI — Settings page:** a new "**Discovery**" section above "Delete account"
  with a number/slider control (1–20, default 10) and a short hint line showing
  the rough cost/time per run at the chosen value (derived, e.g.
  `~$0.02 × N per run`). Persists via the new endpoint.

## Query build → filter → cap order (in `discover()`)

1. Build candidate queries: active-lens **seeds** (verbatim), then **one combined
   role query per active lens**. Dedup.
2. **Exhaustion filter:** drop auto-role queries on cooldown (rule above); keep
   all seeds.
3. **Cap** to the user's effective `discovery_max_searches`.
4. Run each surviving query; count new companies per query.
5. **Record** `discovery_query_stat` for each executed query.

With synonym collapse the query count is usually already well under the cap, so
the cap becomes a safety ceiling rather than the primary limiter — still useful
for users with many lenses/seeds, and as the user-facing knob.

## Validation (implementation-time gate)

Before committing the query/model changes, run a **live A/B** on a real account:
current per-role + gpt-4o discovery vs. combined-query + gpt-4o-mini. Compare the
set of companies surfaced and the run cost. Proceed only if the cheaper path
finds a comparable set of relevant companies; otherwise apply the §1 fallback
(cap distinct role searches) and/or reconsider the model.

## Out of scope

- Direct ATS-board APIs for discovery/re-crawl (a separate, larger feature).
- Per-lens or per-query cost controls (the knob is a single global ceiling).
- Parking user seeds via exhaustion (seeds always run for now).
- Any change to ingest/enrich/scoring cost.

## Migration

One Alembic migration: add `user_settings.discovery_max_searches int NULL` and
create `discovery_query_stat` (with the same RLS policy pattern as other
per-user tables).
