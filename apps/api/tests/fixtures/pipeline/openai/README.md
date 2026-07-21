# OpenAI fixtures

A **mix** of two kinds of payload, and the difference matters when you reason from them:

- **Recorded** — real OpenAI responses captured by `PIPELINE_MODE=record` during live runs
  (`docs/RUNNING-LIVE.md`). Most of the corpus is now this. `embed/` is entirely recorded, which
  is what lets `test_dedup.py` measure real cosine distances between job titles.
- **Hand-authored** — small, plausible-looking placeholders written to exercise
  `RecordedOpenAIClient` and give pipeline stages something to run against. The `acme.*` entries
  are these.

Telling them apart: a recorded `embed/` vector is L2-normalized (‖v‖ ≈ 1.0, as
`text-embedding-3-small` returns); a pseudo-vector is not (‖v‖ ≈ 22).

**Record mode writes by key and does not ask.** A live run will silently overwrite a
hand-authored fixture with whatever the API returned that day — this has already happened once.
Check `git diff` on this directory after any recording run.

## Layout

- `discover/<sha256(queries joined "\n" + "|" + sorted allowed_domains joined ",")>.json` — a
  JSON array of `Source` objects.
- `enrich/<domain-or-name slug>.json` — keyed by the company domain (dots/hyphens pass through
  unchanged, e.g. `acme.com.json`) or, when no domain is known, a slugified `name`. Not a hash,
  so fixtures are easy to find and hand-edit. A JSON object matching `EnrichResult`.
- `extract/<sha256(page_text)>.json` — a JSON object matching `ExtractionResult`.
- `embed/<sha256(text)>.json` — a JSON array of 1536 floats. **These are recorded, real
  embeddings.** `.embed()` is called with a bare posting title, a joined `required_skills` string,
  a joined `role_titles` string, or joined candidate skills — so a fixture is only recoverable to
  its source text if you can guess that text and hash it.
  For any text *without* a fixture, `RecordedOpenAIClient.embed` falls back to a deterministic
  pseudo-vector (seeded from `sha256(text)`), so scoring/dedup tests don't need one fixture per
  skill string. **The pseudo-vector carries no semantic meaning** — only "same text → same vector"
  and "length 1536" are guaranteed. Never draw a conclusion about embedding *distance* from one;
  check ‖v‖ ≈ 1.0 first.
- `rationale/<sha256(json.dumps(factors, sort_keys=True))>.json` — a JSON string.

A miss on `discover`, `enrich`, `extract`, or `rationale` raises `FixtureMissing` naming the
expected path.
