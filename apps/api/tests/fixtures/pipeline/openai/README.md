# OpenAI fixtures

These are HAND-AUTHORED placeholders — small, plausible-looking payloads written to exercise
`RecordedOpenAIClient` and give later pipeline stages something to run against in tests. They are
**not** real OpenAI responses. Once the live smoke test (`pytest -m live`) exists and is run
against a real API key, regenerate these by recording actual responses in the same shape and
replace the placeholders below.

## Layout

- `discover/<sha256(queries joined "\n" + "|" + sorted allowed_domains joined ",")>.json` — a
  JSON array of `Source` objects.
- `enrich/<domain-or-name slug>.json` — keyed by the company domain (dots/hyphens pass through
  unchanged, e.g. `acme.com.json`) or, when no domain is known, a slugified `name`. Not a hash,
  so fixtures are easy to find and hand-edit. A JSON object matching `EnrichResult`.
- `extract/<sha256(page_text)>.json` — a JSON object matching `ExtractionResult`.
- `embed/<sha256(text)>.json` — a JSON array of 1536 floats. **No fixtures are recorded here.**
  `RecordedOpenAIClient.embed` falls back to a deterministic pseudo-vector (seeded from
  `sha256(text)`) for any text without a fixture, so scoring/dedup tests don't need one fixture
  per skill/summary string. The pseudo-vector carries no semantic meaning — only "same text →
  same vector" and "length 1536" are guaranteed.
- `rationale/<sha256(json.dumps(factors, sort_keys=True))>.json` — a JSON string.

A miss on `discover`, `enrich`, `extract`, or `rationale` raises `FixtureMissing` naming the
expected path.
