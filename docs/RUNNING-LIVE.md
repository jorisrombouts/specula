# Running the pipeline live

How to prove the discovery → approval → enrich → crawl → extract → embed → score pipeline
against **real** OpenAI calls (and real ATS traffic), on the demo tenant, and regenerate the
committed recorded fixtures (`apps/api/tests/fixtures/pipeline`) from what it actually returns.

M4 was proven this way — running it live against real ATS boards and a real OpenAI key is what
surfaced (and then fixed) the bugs the fixture suite couldn't see; see `docs/M4-STATUS.md`.
Re-run it when a pipeline contract changes, to re-validate the shapes and refresh the recorded
fixtures. Day-to-day the suite replays `RecordedOpenAIClient`/`RecordedFetcher` fixtures, so most
work needs no live run at all.

## Cost + blast radius

- **Cost:** a handful of OpenAI calls — up to `discovery_max_searches` (5) web-search calls for
  discovery, plus one `enrich_company` call, a handful of `extract_posting` calls (one per
  posting found on the one company you ingest), a couple of `embed` calls, and one `rationale`
  call per scored posting. Cheap (gpt-4o-mini / text-embedding-3-small for most of it), but not
  free.
- **Blast radius:** writes only to the **demo tenant** (`seed.py::DEMO_GOOGLE_SUB`) on **your
  local dev DB** (`localhost:55432`, `docker compose up -d`). It ingests **one company only** —
  a deliberate cost/scope guardrail, not a technical limit.
- **Never** point `DATABASE_URL` at anything but your local dev DB for this.

## 1. Seed the demo user

```
just up       # Postgres + pgvector, if not already running
just migrate
just seed
```

## 2. Run the live pipeline (recording fixtures as it goes)

```
OPENAI_API_KEY=sk-... PIPELINE_MODE=record just prove-live
```

This runs `python -m specula_api.cli prove-live`, which:

1. Runs discovery for the demo user's active lenses/role titles (real OpenAI `web_search`,
   capped at `discovery_max_searches` queries) and stages new approvals.
2. Approves the first approval whose ATS was detected (greenhouse/lever/ashby) and ingests it:
   real `enrich_company`, a real crawl of its ATS board, real `extract_posting` per posting, real
   `embed`, dedup, and real salary-blind `score_posting` + `rationale`.
3. Prints the run stats and the scored postings (title, factor_role, factor_skill, overlap,
   rationale) to stdout.

`PIPELINE_MODE=record` (extends `Settings.pipeline_mode`) wraps the live OpenAI/HTTP clients in
`RecordingOpenAIClient`/`RecordingFetcher` (`apps/api/specula_api/pipeline/{openai_client,http}.py`):
every call still goes out over the network for a real result, which is then also written to
`apps/api/tests/fixtures/pipeline/{openai,http}/...` using the exact key scheme
`RecordedOpenAIClient`/`RecordedFetcher` read from — so this run doubles as regenerating the
fixtures CI replays deterministically.

Fails fast with a clear message if `OPENAI_API_KEY` is unset — it's checked before any DB or
network work.

### Narrower alternatives

Run discovery only, to see what it finds before spending the ingest calls:

```
OPENAI_API_KEY=sk-... PIPELINE_MODE=record just live-discover
```

Then approve + ingest a specific domain from that output:

```
OPENAI_API_KEY=sk-... PIPELINE_MODE=record just live-ingest acme.com
```

## 3. See it rendered in the app

The CLI writes straight to the DB — start the app separately to see the real scored jobs render:

```
just dev-api          # PIPELINE_MODE unset → defaults to "live"; irrelevant here, we're only reading
just dev-web-noauth   # bypasses Google sign-in for local viewing
```

Open the web app and browse the demo user's Jobs / Insights / Approvals views — they should now
show the real company/posting(s) `prove-live` ingested, with real extracted fields and a real
LLM-written rationale, alongside the pre-existing seeded demo data.

## 4. Commit the regenerated fixtures

```
git status apps/api/tests/fixtures/pipeline
git diff apps/api/tests/fixtures/pipeline
```

Only the `openai/*` recordings are committed:

```
git add apps/api/tests/fixtures/pipeline/openai
git commit -m "test(api): regenerate recorded pipeline fixtures from a live run"
```

**`http/*.json` is gitignored** — a real run mirrors every fetched page, which is hundreds of
MB of raw ATS/company HTML. The suite never replays those: a live run records against the
REAL urls/queries while the tests replay small hand-authored "acme" fixtures, so the two sets
are disjoint and a live run does NOT regenerate what CI replays. The tests' own http fixtures
are already tracked and keep working; add a new hand-authored one with `git add -f`.

Re-run the full suite afterward (`cd apps/api && uv run pytest -q`). Note the live run's real
value is proving the pipeline against real responses — pipeline contract changes it forces
(query shape, page-text reduction, relevance gating) are what break the recorded tests, far
more than field-level shape drift.
