# Specula — Production Engineering Specification

> **Purpose.** This document specifies how to build **Specula** as a real, multi-tenant SaaS
> product. It supersedes the prototype reproduction spec (preserved as
> `Specula - Design Spec (prototype).md`). The prototype (`Specula.html` + `specula/*`) remains
> the **pixel-faithful visual source of truth** for the UI; this spec wires that exact design to
> a production frontend, backend, data pipeline, and infrastructure.
>
> **How to use this doc.** Build in the order of §18 (milestones). The frontend must port the
> prototype's look 1:1 — when this spec and the prototype disagree on visuals, the prototype
> wins; when they disagree on architecture/data/behavior, this spec wins. Anything marked
> **[DECISION]** records a non-obvious call and its rationale; **[OPEN]** flags something the team
> must confirm before/within the relevant milestone.

> **Reconciled with CLAUDE.md (2026-07-10). CLAUDE.md governs on conflict.** Applied: no billing /
> Stripe / plan tiers / entitlement gating; no object storage (provenance = `content_hash` +
> `source_url`; logos = favicon URL); Next.js 16; Google-only auth (JWT stateless, no DB adapter);
> low-confidence threshold = 50. **Pipeline is currently manual-trigger only — the weekly scheduler
> and its background-worker/queue/hosting infra are deferred to a later milestone.**

---

## 0. Concept & positioning (unchanged from prototype)

Specula is a personal **"role ledger"** — not a job board, not an applicant CRM. Each user
maintains a private, deduplicated pool of roles, **scored against who they are and what they
want**. The product's premise (and its moat vs. generic trackers) is that it *parses* every
posting into a structured "insight record," which unlocks per-role match scoring and personal
market-intelligence aggregates.

The aesthetic is an **editorial instrument**: warm paper, Spectral serif display, Geist Mono
numerics, calm and authoritative. Four signature interactions carry the craft: the assembling
intro, the animated lens re-sort, the match-score "scoring" reveal, and the row→drawer
shared-element morph (§13). Production must preserve all four.

---

## 1. Product scope & v1 boundaries

**In scope for v1 (multi-tenant SaaS):**
- Email-based accounts with full **per-user data isolation** (every domain row is tenant-scoped).
- The full app surface from the prototype: Jobs + lenses, Job drawer, Approval queue, Companies
  registry, Insights, Search profiles, Candidate profile, Targeting.
- **Discovery pipeline** via web scraping/crawling of company career pages, with an **approval
  queue** gate before a company enters a user's registry.
- **LLM extraction** of postings into insight records + **LLM-assisted match scoring** with
  structured (schema-validated) output, using **OpenAI**.
- **Scheduled** weekly discovery/refresh per user + **on-demand** "Refresh now."
- Persisted user state (statuses, notes, feedback, lens/targeting/candidate edits, tweaks).

**Explicitly out of v1 (spec the seams, don't build):**
- ATS API integrations (Greenhouse/Lever/Ashby official APIs) — design the `source` abstraction
  so they can be added later, but v1 discovery is scraping.
- Email/push notifications, team/multi-seat orgs, mobile apps.
- CV upload/parsing (Candidate profile stays an explicit user-controlled form, per product intent).
- Auto-apply or outbound messaging.

---

## 2. System architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Browser (desktop-first SPA-feel, Next.js App Router)                     │
└───────────────▲───────────────────────────────────────────┬─────────────┘
                │ HTTPS (session cookie / JWT)                │
                │                                             │
   ┌────────────┴───────────────┐               ┌────────────▼─────────────┐
   │  Vercel                     │   server-to-  │  Container host           │
   │  • Next.js 16 (App Router)  │   server      │  (Fly.io / Railway /      │
   │    SSR/RSC + UI             │   (signed     │   Render)                 │
   │  • Auth (Auth.js)           │   service     │  • FastAPI (Python 3.12)  │
   │  • Thin BFF route handlers  │   token)      │    REST API               │
   │    proxy → FastAPI          ├──────────────►│  • Worker (Celery/Arq)    │
   │                              │               │  • Scheduler (beat/cron)  │
   └────────────┬───────────────┘               └───────────┬──────────────┘
                │                                            │
                │                                            │
                ▼                                            ▼
        ┌───────────────┐   ┌──────────────┐   ┌─────────────────────────┐
        │ Neon Postgres │   │ Redis (queue │   │ OpenAI API              │
        │ + pgvector    │   │ + cache +    │   │ (extraction + scoring,  │
        │ (tenant data) │   │  rate limit) │   │  structured outputs)    │
        └───────────────┘   └──────────────┘   └─────────────────────────┘
```

### [DECISION] Why a split deployment (Vercel + container host)
You chose FastAPI for the backend (right call — the ML/scoring/scraping work is Python-native)
**and** Vercel for infra. Vercel serverless can't run a long-lived FastAPI app with a queue,
scheduler, and minutes-long scraping/LLM jobs. So:
- **Vercel** hosts the **Next.js app** (UI, RSC/SSR, Auth.js) and a **thin BFF**:
  Next route handlers that authenticate the user and proxy to FastAPI with a signed service token.
  The browser never talks to FastAPI directly.
- **A container host** (Fly.io recommended; Railway/Render fine) runs **FastAPI**, the **worker**,
  and the **scheduler**. Long jobs live here.
- **Neon** is the single source of truth, reachable from both (use Neon's pooled connection string
  from Vercel/serverless; direct connection from the always-on Python services).
- **Redis** (Upstash works from both) backs the job queue, caching, and rate limiting.

If the team prefers a single platform, an acceptable alternative is **all-Python-on-a-container**
with Next.js also containerized there and Vercel dropped — but the chosen target is Vercel for the
web tier, so the split above is the spec.

### Monorepo layout
```
specula/
  apps/
    web/                      # Next.js 16 (App Router, TS, Tailwind) — deploys to Vercel
      app/                    # routes: (app)/jobs, /companies, /insights, /profiles, ...
      components/             # ported prototype components (see §12)
      lib/                    # api client, auth, formatting, hooks
      styles/                 # tokens.css + tailwind layer
    api/                      # FastAPI (Python 3.12) — deploys to container host
      specula_api/
        main.py               # app factory, routers
        routers/              # jobs, companies, approvals, lenses, candidate, targeting, insights, runs
        services/             # scoring, extraction, dedup, enrichment, insights aggregation
        pipeline/             # discovery crawler, fetchers, parsers, source adapters
        workers/              # task definitions (Arq/Celery)
        scheduler/            # periodic schedules
        db/                   # SQLAlchemy models, migrations (Alembic)
        schemas/              # Pydantic request/response + LLM structured-output models
        core/                 # config, auth, tenancy, logging, rate limit
  packages/
    shared-types/             # OpenAPI-generated TS types consumed by web (see §8)
  infra/                      # IaC, Dockerfiles, fly.toml / render.yaml, GH Actions
  prototype/                  # the original HTML prototype, kept as visual reference
```

---

## 3. Tech stack (pinned)

| Layer | Choice | Notes |
|---|---|---|
| Web framework | **Next.js 16**, App Router, React 19, TypeScript (strict) (Turbopack production builds) | RSC for data-heavy views; client components for the animated surfaces. |
| Styling | **Tailwind CSS v4** with design tokens as theme (see §11) | Pixel-faithful port; tokens map 1:1 to prototype CSS variables. |
| Web auth | **Auth.js (NextAuth v5)**, OAuth (Google) only | Session cookie; server token minted for BFF→API calls. |
| Web data | Server Components + route handlers (BFF); **TanStack Query** for client mutations/optimistic UI | Animated views need client cache; lists can be RSC-fetched. |
| Backend | **FastAPI** (Python 3.12), Pydantic v2 | REST, OpenAPI 3.1 emitted for type-gen. |
| ORM / migrations | **SQLAlchemy 2.0** + **Alembic** | Async engine. |
| DB | **Neon Postgres** + **pgvector** | Serverless Postgres; embeddings for skill/role similarity & dedup. |
| Queue / cache | **Redis** (Upstash) + **Arq** (async) — or Celery if team prefers | Background jobs, rate-limit buckets, response cache. |
| Scheduler | Arq cron / Celery beat (in the container) | Per-user weekly runs; staggered. |
| LLM | **OpenAI** (e.g. `gpt-4o` / `gpt-4o-mini` tiers) via **structured outputs** (JSON schema) | Extraction on mini-tier, scoring rationale on full-tier. See §6. |
| Embeddings | OpenAI `text-embedding-3-small` (1536-d) | Skill/role vectors; stored in pgvector. |
| Discovery (seeding) | **OpenAI Responses API `web_search` tool** (domain-filterable), harvest `sources` URLs | Finds candidate companies/careers URLs; ingestion is separate. §5. |
| Scraping (ingestion) | `httpx` + `selectolax`/`BeautifulSoup`; **Playwright** for JS-rendered career pages | Fetch + snapshot the actual postings. Politeness controls in §15. |
| Observability | Sentry (web + api), structured JSON logs, OpenTelemetry traces | §16. |
| CI/CD | GitHub Actions → Vercel (web) + Fly/Render (api) | §16. |

---

## 4. Data model & database schema

**Multi-tenancy model.** Single shared database; every user-owned row carries `user_id`. Enforce
isolation at **two layers**: (1) every query is scoped by `user_id` in the data-access layer, and
(2) **Postgres Row-Level Security (RLS)** policies as a backstop (set `app.user_id` per
transaction). Global/shared reference data (e.g. canonical skill taxonomy) lives in unscoped tables.

### 4.1 Core tables (DDL sketch — Postgres + pgvector)

```sql
create extension if not exists vector;
create extension if not exists pg_trgm;        -- fuzzy company/title matching for dedup

-- ── accounts ────────────────────────────────────────────────────────────
create table users (
  id              uuid primary key default gen_random_uuid(),
  email           citext unique not null,
  name            text,
  created_at      timestamptz not null default now()
);

-- ── candidate profile (1:1 with user) ──────────────────────────────────
create table candidate_profiles (
  user_id     uuid primary key references users(id) on delete cascade,
  headline    text, location text, work_mode text, visa text,
  years       int, education text,
  languages   text[] default '{}',
  skills      text[] default '{}',                       -- explicit, user-controlled
  projects    jsonb default '[]',                        -- [{name, note}]
  experience  jsonb default '[]',                        -- [{role, org, period}]
  skills_vec  vector(1536),                              -- embedding of skills+headline
  updated_at  timestamptz not null default now()
);

-- ── targeting (global baseline, 1:1 with user) ─────────────────────────
create table targeting (
  user_id     uuid primary key references users(id) on delete cascade,
  role_titles text[] default '{}',                       -- synonyms
  seniority   text[] default '{}',
  must_haves  text[] default '{}',
  avoid       text[] default '{}',
  preferences text,                                      -- free-text soft signal
  -- NOTE: no salary fields by design (§ product rule)
  updated_at  timestamptz not null default now()
);

-- ── lenses (search profiles) ───────────────────────────────────────────
create table lenses (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references users(id) on delete cascade,
  name        text not null, short text,
  scope       text,            -- hard: location scope
  modes       text[] default '{}',  -- hard: allowed work modes
  origin_rule text,            -- hard: 'any' | 'foreign_hq' | ...
  focus       text,            -- soft signal
  seeds       text[] default '{}',  -- discovery query seeds (auto-generated, editable)
  active      boolean not null default true,
  is_default  boolean not null default false,            -- the 'All' lens
  created_at  timestamptz not null default now()
);
create index on lenses(user_id);

-- ── companies (per-user registry; approved companies) ──────────────────
create table companies (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references users(id) on delete cascade,
  name        text not null, domain text, logo_url text,
  ats         text,                                       -- greenhouse|lever|ashby|custom
  careers_url text,
  hq_country  text, hq_confidence int,                    -- 0..100
  comp_estimate text,                                     -- coarse '€€'/'€€€'
  tracking    boolean not null default true,
  status      text not null default 'approved',           -- approved|rejected|snoozed|pending
  added_at    timestamptz not null default now(),
  unique (user_id, domain)
);
create index on companies(user_id);

-- ── postings (raw + extracted insight record) ─────────────────────────
create table postings (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references users(id) on delete cascade,
  company_id    uuid references companies(id) on delete set null,
  source        text not null,            -- 'scrape'
  source_url    text not null,
  content_hash  text not null,            -- for change-detection / dedup
  -- extracted insight record (LLM, schema-validated):
  title         text, role_family text,
  city text, country text, hq_country text, work_mode text,
  seniority text, education text,
  required_skills text[] default '{}', nice_to_have text[] default '{}',
  visa text, languages text[] default '{}', contract text, geo text,
  salary_text   text,                     -- only if stated; never used to rank
  deadline_at   date, posted_at date,
  responsibilities text[] default '{}',
  summary       text,
  still_open    boolean default true,
  extraction_confidence int,              -- 0..100
  title_vec     vector(1536),             -- role embedding (dedup + role factor)
  skills_vec    vector(1536),             -- required-skills embedding
  first_seen_at timestamptz not null default now(),
  last_seen_at  timestamptz not null default now(),
  dedup_group   uuid,                      -- postings judged the same role cluster
  unique (user_id, content_hash)
);
create index on postings(user_id);
create index on postings using ivfflat (skills_vec vector_cosine_ops);

-- ── scores ─────────────────────────────────────────────────────────────
-- Lens-INDEPENDENT part is 1:1 with posting (role & skill never depend on a
-- lens). The location factor and the overall index are LENS-AWARE and computed
-- at read time (cheap, rule-based) for the active lens — see §6.2.
create table scores (
  posting_id    uuid primary key references postings(id) on delete cascade,
  user_id       uuid not null references users(id) on delete cascade,
  factor_role   int not null, factor_skill int not null,   -- lens-independent, persisted
  overlap_matched int not null, overlap_total int not null,
  red_flag      text,                     -- one-way penalty reason, nullable
  rationale     text not null,            -- LLM-written 'why' (role/skill based), shown on the row
  scored_with   text not null,            -- model + scoring-version for reproducibility
  scored_at     timestamptz not null default now()
  -- NOTE: factor_loc + overall `match` are derived per active lens at read time,
  -- not stored here. Optionally cache them in (posting_id, lens_id) if profiling demands.
);

-- ── user state on a posting (status, notes, feedback) ──────────────────
create table posting_state (
  posting_id uuid primary key references postings(id) on delete cascade,
  user_id    uuid not null references users(id) on delete cascade,
  status     text,                        -- null|Saved|Applied|Interviewing|Offer|Dismissed
  note       text,
  dismiss_reason text,
  feedback   text,                        -- 'positive'|'negative'|null  (steers scoring)
  updated_at timestamptz not null default now()
);

-- ── approval queue (candidate companies awaiting decision) ─────────────
create table approvals (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  name text, domain text, logo_url text, ats text,
  hq_country text, found_query text, why text,
  open_roles int default 0, hq_confidence int,
  decision   text,                        -- null|approve|reject|snooze
  created_at timestamptz not null default now()
);
create index on approvals(user_id) where decision is null;

-- ── discovery runs (provenance for 'synced Nd ago' + Insights) ─────────
create table runs (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  kind       text not null,               -- 'scheduled' | 'on_demand'
  status     text not null default 'queued', -- queued|running|done|error
  started_at timestamptz, finished_at timestamptz,
  stats      jsonb default '{}',          -- {found, new, closed, low_conf_excluded, errors}
  created_at timestamptz not null default now()
);

-- ── canonical skill taxonomy (GLOBAL, unscoped) ────────────────────────
create table skills_taxonomy (
  id     uuid primary key default gen_random_uuid(),
  canonical text unique not null,
  aliases   text[] default '{}',
  vec       vector(1536)
);
```

### 4.2 The configuration model: who/what vs where/how
Three config surfaces, each answering exactly one question — **no overlap**:
- **Candidate** (`candidate_profiles`) — *who I am*: skills, experience, education. Drives scoring's
  left-hand side. `work_mode`/`location` here are **personal descriptors only** — used as defaults
  to pre-fill the first lens at onboarding; they are **never** a filter or scoring input themselves.
- **Targeting** (`targeting`) — *what I want & my values*: role-title synonyms, seniority,
  must-haves, avoid, free-text preferences. **Owns role identity & values. Holds NO geography.**
  Global; applies to every lens.
- **Lenses** (`lenses`) — *where & how I'm looking*: location scope, work mode, HQ origin rule
  (+ a soft focus signal and discovery seeds). **Lenses own geography & mode entirely.** A role is
  ingested once and scored once on its lens-independent dimensions; lenses re-slice the shared pool
  and make the location factor lens-aware (§6.2).

This split is the rule of thumb for where any new setting belongs: identity/values → Targeting;
anything geographic or mode-related → Lenses. (We do **not** collapse Targeting into the default
lens — keeping it a separate global object means must-haves/avoid apply everywhere with zero
inheritance logic. Onboarding, not consolidation, solves the "three empty screens" problem — §7.9.)

### 4.3 Lenses, counts, and the "single shared pool" rule
The prototype's hard rule — **all counts are derived, never stored** — carries over. `lenses.count`
/ `isNew` do **not** exist as columns; the API computes them per request by applying lens filters to
the user's posting pool. Lens filtering is the production analog of `filterByLens` (§4.6 of the
prototype spec): translate each lens's `scope`/`modes`/`origin_rule` into SQL `WHERE` clauses over
`postings` joined to `companies`. "Foreign HQ" = `postings.hq_country <> postings.country`, etc.

### 4.4 What replaces the prototype's `window.SPECULA`
The seed object becomes seven tenant-scoped tables above. Seed data from the prototype (the
~13 EU AI roles, companies, approvals, candidate "Joris") ships as a **demo-account seeder** used
for onboarding/empty-state previews and E2E tests — not as the app's data source.

---

## 5. The discovery → insight pipeline

A **run** (scheduled or on-demand) executes this pipeline for one user. Each stage is an idempotent
worker task; stages communicate via the queue and write to Postgres.

> **Current status:** the pipeline runs on a **manual trigger only** (on-demand "Refresh now"),
> executed inline. The **scheduled** weekly run described below, and the background-worker/queue/
> hosting infra it needs, are **deferred to a later milestone** (§7).

1. **Seed query generation.** For each active lens, combine `targeting.role_titles` (synonyms) +
   lens `seeds` + lens `scope` into a small set of natural-language discovery queries.
2. **Company discovery via OpenAI web search.** Run those queries through the **OpenAI Responses
   API `web_search` tool**, optionally **domain-filtered** (`filters.allowed_domains`, up to 100) to
   ATS hosts (`greenhouse.io`, `lever.co`, `ashbyhq.com`) or a target company set. Harvest the
   response's **`sources`** array (the full list of URLs the model consulted — broader than inline
   citations) as candidate career-page / posting URLs. Resolve these (plus already-approved
   companies' link graphs) into candidate companies. New companies are written to `approvals`
   (status `null`) with a `found_query` and an LLM-written `why`. **They do not enter the pool until
   the user approves** (§7.3). Approved companies are enriched (HQ country + confidence via
   LLM+heuristics, logo, ATS detection) — `logo_url` holds a favicon URL, not an object-storage
   asset.
   - *Division of labor:* OpenAI **finds** (discovery/seeding only); Specula **fetches** (step 3).
     We never rely on the model for full-page posting content — we fetch it ourselves so
     provenance and change-detection are under our control.
   - *Cost:* each search is a billable tool call; cap searches per run and cache by
     `(query, week)`.
3. **Posting fetch.** For each tracked company, fetch its careers/ATS listing pages
   (`httpx`; `Playwright` when JS-rendered). Compute `content_hash` from the fetched HTML
   (change-detection/dedup); do not persist raw HTML. Skip unchanged postings (hash hit) to control
   cost.
4. **Extraction (LLM, structured output).** Turn each new/changed posting into the insight record
   (§6.1). Validate against the Pydantic/JSON schema; on low confidence, **store but flag**
   (`extraction_confidence < 50`) — surfaced in UI as "surfaced, not trusted," excluded from
   Insights aggregates.
5. **Dedup.** Cluster postings that are the same role across sources/lenses using
   `(company, normalized_title)` trigram match **and** cosine similarity of `title_vec`
   (threshold tuned, ~0.92). Assign a shared `dedup_group`; the pool is deduped on read.
6. **Scoring (LLM-assisted, §6.2).** Compute `match`, the three factors, skill overlap, optional
   `red_flag`, and a one-sentence `rationale`. Persist to `scores` with `scored_with` (model +
   scoring version) for reproducibility.
7. **Lifecycle upkeep.** Mark postings whose source 404s / disappears as `still_open=false`; a
   company's open-role count is **derived** from its still-open postings (no stored counter to
   decrement).
8. **Run finalize.** Write `runs.stats` (`{found, new, closed, low_conf_excluded, errors}`) and
   `finished_at`. The sidebar's "synced Nd ago · N new" reads the latest finished run.

**[DECISION] Discovery uses OpenAI's built-in web search; ingestion is ours.** Seeds become URLs
via the Responses API `web_search` tool (domain-filtered to ATS hosts where useful), harvesting the
`sources` URL list — no separate Bing/SerpAPI contract needed in v1. The model only **discovers**;
the actual posting fetch, change-detection (`content_hash`), and extraction (§6) remain in our
pipeline so we own provenance and cost. Keep the `pipeline/source` abstraction so an official ATS
feed or alternate search provider can be swapped in later. Onboarding may still let users seed a few
companies directly to bootstrap a cold account.

> Note: if Specula ever shows raw web-search results to end users, OpenAI requires inline citations
> to be visible and clickable. Our pipeline consumes the URLs server-side (not shown as a search
> UI), so this applies only if a "how we found this" surface is added.

---

## 6. LLM extraction & scoring (OpenAI, structured outputs)

All model calls use **structured outputs** (response bound to a JSON schema) so results are
schema-valid and directly persistable. Keep a `scoring_version` constant; bump it when prompts or
the formula change so historical scores remain interpretable.

### 6.1 Extraction
- **Input:** cleaned posting text (strip nav/boilerplate), company context, source URL.
- **Model:** cost-efficient tier (e.g. `gpt-4o-mini`) — extraction is mostly transcription.
- **Output schema:** the insight-record fields in §4.1 `postings` (title, role_family, city,
  country, hq_country, work_mode, seniority, education, required_skills[], nice_to_have[], visa,
  languages[], contract, geo, salary_text|null, deadline_at|null, posted_at|null,
  responsibilities[], summary, still_open, **extraction_confidence 0–100**).
- **Rules baked into the prompt:** never invent salary (null unless explicitly stated); normalize
  skills toward the canonical taxonomy; set `extraction_confidence` honestly (low when the page is
  ambiguous/JS-garbled).
- **Embeddings:** after extraction, embed required-skills and title → `skills_vec`, `title_vec`.

### 6.2 Match scoring (lens-aware)
Hybrid, explainable, **salary-blind**. **Role and skill factors are lens-independent** (computed
once per posting); the **location factor and the overall index are lens-aware** (computed per active
lens at read time):
- **Skill factor (deterministic core, lens-independent):** required-skill overlap = matched/total
  against the candidate's `skills` (canonicalized), blended with cosine similarity of
  `postings.skills_vec` vs `candidate_profiles.skills_vec`. Produces `factor_skill` (0–100) and
  `overlap_matched/total`. Persisted in `scores`.
- **Role factor (lens-independent):** cosine similarity of `title_vec` vs the user's `role_titles`
  embedding, adjusted for seniority match. Produces `factor_role`. Persisted in `scores`.
- **Location factor (LENS-AWARE):** rule-based fit of the posting against the **active lens's**
  scope + work mode + HQ-origin rule, plus visa fit. Produces `factor_loc` **for that lens** — the
  same role scores differently under "Remote · EU" vs "Berlin core." Computed at read time; not
  stored on the 1:1 `scores` row (optionally cached per `(posting, lens)`).
- **Overall `match` (LENS-AWARE):** weighted blend (default `role .4 / skill .4 / loc .2`) of the
  two persisted factors + the lens's `factor_loc`, then a **one-way red-flag penalty**: if
  `factor_skill` is very low (e.g. <45) or a must-have is absent, cap/penalize and set `red_flag`.
  Feedback signals (§7.2) nudge weights: recent `negative` examples down-weight similar roles;
  `positive` up-weight. (v1: simple, transparent adjustment; keep it auditable.)
- **Rationale:** a single LLM call (full tier) produces the one-sentence `rationale` shown on the
  row, **given the computed factors** (so prose matches the numbers, never drives them).

**[DECISION] Numbers are computed, prose is generated.** The 0–100 and the three factors come from
deterministic/embedding logic, not from "ask the model for a score." This keeps scoring stable,
cheap to recompute, explainable, and immune to prompt drift. The LLM only *narrates*.

**[DECISION] The score is lens-aware on location.** Switching a lens genuinely re-scores roles on
the location dimension (and thus re-ranks the pool) — so the centerpiece lens re-sort animation
(§13 / prototype §9.2) is conceptually honest, not cosmetic. Role/skill stay constant across lenses;
only `factor_loc` and the overall index move. Because `factor_loc` is cheap and rule-based, this is
computed at read time per lens with no extra LLM cost. The `rationale` text is written from the
lens-independent role/skill factors, so it stays valid across lenses (location nuance lives in the
LOC bar, not the prose).

---

## 7. Background jobs & scheduling

> **Current status:** the pipeline is **manual-trigger only** — on-demand "Refresh now", run inline.
> **Scheduled runs (below) are deferred to a later milestone**, along with the background-worker/
> queue and hosting infra this section assumes.

- **Scheduled runs (deferred):** one `scheduled` run per active user per week, **staggered** across
  the week by hashing `user_id` (avoid thundering herd + smooth LLM/scrape spend). Skip dormant users
  (no login in N weeks) to control cost; resume on next login.
- **On-demand "Refresh now":** enqueues an `on_demand` run for that user (rate-limited, e.g. ≤ a few
  per hour). The button's spin state maps to `runs.status` (`queued`/`running` → spinning;
  `done` → "just now"). UI polls run status (or subscribes via SSE) and refreshes lists on completion.
- **Idempotency & retries:** every task keyed by `(run_id, stage, target)`; safe to retry. Backoff
  on scrape/LLM errors; per-run error budget recorded in `runs.stats.errors`.
- **Concurrency & politeness:** per-domain crawl concurrency caps + delay; global LLM concurrency cap.

---

## 8. API contract (FastAPI, REST)

- **Style:** REST, JSON, `/api/v1/*`. FastAPI emits **OpenAPI 3.1**; generate `packages/shared-types`
  (TypeScript) from it in CI so web and API never drift.
- **Auth:** the browser holds a Next.js/Auth.js session. Next BFF route handlers attach a **signed
  service JWT** (short-lived, contains `user_id`) on calls to FastAPI. FastAPI validates it and sets
  the tenant context (`app.user_id` for RLS) for the request. FastAPI is **not** publicly browser-
  facing.
- **All list endpoints are tenant-scoped automatically** (never accept a `user_id` from the client).

| Method & path | Purpose |
|---|---|
| `GET /jobs?lens={id}&sort={match\|deadline\|new}` | Deduped, scored pool for a lens; includes derived per-lens meta. |
| `GET /jobs/{id}` | Full insight record + score + state (drawer). |
| `PATCH /jobs/{id}/state` | Set status / note / feedback / dismiss reason. |
| `GET /lenses` / `POST /lenses` / `PATCH /lenses/{id}` / `DELETE` | Manage lenses; responses include derived counts. |
| `GET /companies` / `PATCH /companies/{id}` | Registry; toggle tracking, edit. |
| `GET /approvals` / `POST /approvals/{id}/decision` | Queue + approve/reject/snooze (approve → enrich + add to companies). |
| `GET /candidate` / `PUT /candidate` | Candidate profile (re-embeds skills on write). |
| `GET /targeting` / `PUT /targeting` | Global baseline. |
| `GET /insights?period={4w\|8w\|q}` | Aggregates (excludes low-confidence). |
| `GET /skills-gap` | Derived missing-skills vs target roles. |
| `POST /runs` / `GET /runs/{id}` / `GET /runs/latest` | Trigger on-demand refresh; poll status; sidebar sync info. |
| `GET /runs/stream` (SSE) | Live run progress (optional; polling fallback). |

Mutations return the updated resource so the client can reconcile optimistic UI.

---

## 9. Auth & multi-tenancy

- **Auth.js (NextAuth v5)** on Vercel: Google OAuth only. JWT (stateless) session (no DB adapter);
  FastAPI owns the DB. Session via secure, httpOnly cookie. On sign-in, ensure a `users` row + empty
  `candidate_profiles`/`targeting`/default `All` lens exist (idempotent bootstrap).
- **Tenancy:** every domain query filtered by `user_id` in the data layer **and** guarded by RLS
  policies (`using (user_id = current_setting('app.user_id')::uuid)`). FastAPI sets
  `app.user_id` at the start of each request transaction from the validated service JWT.

---

## 10. Frontend architecture (Next.js App Router)

- **Routing:** real routes replace the prototype's `view` string — `/(app)/jobs`,
  `/(app)/approvals`, `/(app)/companies`, `/(app)/insights`, `/(app)/profiles`, `/(app)/targeting`,
  `/(app)/candidate`. A shared `(app)/layout.tsx` renders the **Sidebar** + main scroll column.
- **Server vs client components:**
  - **RSC fetch** the initial list/aggregate data (Jobs list, Companies, Insights) on the server for
    fast first paint.
  - The **animated surfaces are client components**: the Jobs list (FLIP re-sort), the Drawer (morph
    + scoring reveal), the IntroOverlay, the MatchMeter, and the Tweaks panel.
  - Use **TanStack Query** for mutations and optimistic updates (status change, dismiss, approve,
    lens edits) so the FLIP/exit animations have local state to animate, then reconcile with server.
- **State that was local in the prototype** (status, dismissals, feedback, tweaks) now persists via
  the API; **tweaks** persist per-user (small `user_settings` JSON or localStorage mirror for
  instant apply, synced to server).
- **Data fetching contract:** the Jobs list endpoint already returns deduped, scored, lens-filtered
  rows with derived counts, so the client renders and animates without recomputing scores.
- **Loading/empty/error states:** real ones now — skeleton job rows during a run; the "Refresh now"
  spin bound to run status; empty pool prompts onboarding (add companies). (This realizes Tier-2
  item #6 from the product backlog.)
- **Accessibility & no-JS:** core lists render from RSC HTML; animations are progressive enhancement
  gated on `prefers-reduced-motion` and hydration.

---

## 11. Design system → Tailwind theme

Port the prototype tokens **exactly** into the Tailwind theme (and a `tokens.css` `@layer base` for
the runtime-swappable ones the Tweaks panel mutates). Values are canonical from the prototype.

```css
/* styles/tokens.css — :root holds the live, tweakable variables */
:root {
  --paper:#FBFAF6; --panel:#F4F2EB; --panel-2:#EEEBE1; --card:#FFFFFF;
  --ink:#211E18; --ink-2:#7C7567; --ink-3:#ABA493; --rule:#E4E0D5; --rule-2:#D6D1C2;
  --accent:#2E7D4F; --accent-bg:#E7F0E9; --accent-ink:#1E5D39;
  --warn:#B3541E; --warn-bg:#F7EBE0; --gold:#9A7A18;
  --font-display:'Spectral',serif; --font-body:'Hanken Grotesk',sans-serif;
  --font-mono:'Geist Mono',monospace;
  --shadow-card:0 1px 2px rgba(33,30,24,.04);
  --shadow-pop:0 16px 50px -12px rgba(33,30,24,.28),0 2px 8px rgba(33,30,24,.08);
}
[data-density="compact"]{ /* row/gutter/card-pad overrides per prototype */ }
```

```ts
// tailwind theme maps tokens → utilities (color names mirror the variables)
export default {
  theme: { extend: {
    colors: {
      paper:'var(--paper)', panel:'var(--panel)', 'panel-2':'var(--panel-2)', card:'var(--card)',
      ink:'var(--ink)', 'ink-2':'var(--ink-2)', 'ink-3':'var(--ink-3)',
      rule:'var(--rule)', 'rule-2':'var(--rule-2)',
      accent:'var(--accent)', 'accent-bg':'var(--accent-bg)', 'accent-ink':'var(--accent-ink)',
      warn:'var(--warn)', 'warn-bg':'var(--warn-bg)', gold:'var(--gold)',
    },
    fontFamily:{ display:['var(--font-display)'], body:['var(--font-body)'], mono:['var(--font-mono)'] },
    boxShadow:{ card:'var(--shadow-card)', pop:'var(--shadow-pop)' },
  }},
}
```
Typography scale, density rules, and the layout shell (`grid-cols-[236px_1fr] h-screen`) are ported
verbatim from §2 of the prototype spec. Fonts via `next/font` (Spectral, Hanken Grotesk, Geist Mono;
plus Newsreader & Source Serif 4 for the font Tweak). The Tweaks panel mutates the `:root` variables
and `data-*` attributes exactly as in the prototype.

---

## 12. Component & view inventory (port targets)

The prototype's component and view specs are **normative** and reproduced in
`Specula - Design Spec (prototype).md` §3 and §5–§8. Port each to a typed React component; the source
files map as follows:

| Prototype (`specula/*`) | Production (`apps/web/components/*`) | Data source |
|---|---|---|
| `ui.jsx` → `MatchMeter`, `OverlapBar`, `Icon`, `useCountUp` | `match-meter.tsx`, `overlap-bar.tsx`, `icon.tsx`, `hooks/use-count-up.ts` | props only |
| `jobs.jsx` → `JobsView`, `JobRow`, `Drawer` | `jobs/jobs-view.tsx` (client), `job-row.tsx`, `job-drawer.tsx` | `GET /jobs`, `/jobs/{id}` |
| `pipeline.jsx` → `ApprovalsView`, `CompaniesView` | `approvals/*`, `companies/*` | `/approvals`, `/companies` |
| `intel.jsx` → `InsightsView` | `insights/insights-view.tsx` | `/insights`, `/skills-gap` |
| `config.jsx` → `ProfilesView`, `CandidateView`, `TargetingView`, `TagEditor` | `profiles/*`, `candidate/*`, `targeting/*`, `tag-editor.tsx` | `/lenses`, `/candidate`, `/targeting` |
| `intro.jsx` → `IntroOverlay` | `intro-overlay.tsx` (client) | none |
| `app.jsx` → Sidebar, routing, tweaks | `(app)/layout.tsx`, `sidebar.tsx`, `tweaks-panel.tsx` | `/runs/latest`, user settings |

Behavioral parity required: derived counts, salary-blindness, red-flag treatment, low-confidence
"surfaced, not trusted," `data-screen-label` on each view root for analytics/QA.

---

## 13. The four signature moments (production notes)

All four port directly; they're already framework-agnostic DOM/WAAPI techniques. Implement in client
components, gate on `prefers-reduced-motion`, and ensure they survive hydration.

- **9.1 Assembling intro** — `IntroOverlay`. Keep "once per session" via `sessionStorage`. Show only
  after auth, on first app load of a session. Add the optional "replay intro" affordance in Settings.
- **9.2 Animated lens re-sort (FLIP)** — unchanged technique. Because data now comes from `GET /jobs`,
  keep the previously-rendered list in client state and FLIP from old → new on lens/sort change while
  the new list resolves; meters re-sweep via the `replay` key. Respect reduced-motion.
- **9.3 Match scoring reveal** — for drawer opens **not** from a row (e.g. command palette, deep link).
- **9.4 Row → drawer shared-element morph** — capture row `.jtitle`/`.meter` rects on click, animate
  the drawer's title+meter from them (font-ratio scale for the title, width-ratio for the meter),
  `setTimeout` fallback on close. With a router-driven drawer (`/jobs/{id}` as an intercepting route),
  pass the captured rects via client state, not the URL.

Reference §9 of the prototype spec for exact durations, easings, and the gotchas (no compounding
parent transform; clamp scale `[0.3,1.4]`).

---

## 14. Motion & accessibility (carry over)

Same principles as the prototype §10: short entrances (0.4–0.6s), bar/ring sweeps ~0.8–0.9s, rAF
count-ups, **no infinite decorative loops** except the sidebar sync-dot pulse, honor
`prefers-reduced-motion` for intro/FLIP/entrances/morph. Desktop-first dense instrument; AA contrast
on `--ink-2`/paper; min 11px text with mono carrying small labels. Add real focus states and keyboard
operability (the prototype was mouse-first) — Tab/arrow nav in the Jobs list, Esc closes the drawer.

---

## 15. Scraping, privacy & compliance

**Scraping career pages is the approach — do it freely, do it politely.** Public job listings are
fair game to fetch and parse; the requirements below keep us a good web citizen and reduce both
legal and getting-blocked risk. This is a set of *requirements*, not a reason to hesitate.

- **Be polite (required):** respect `robots.txt`; per-domain rate limits + delays; identify via a
  descriptive User-Agent with a contact URL; cache via `content_hash` to avoid re-fetching unchanged
  pages; back off on 429/5xx.
- **Prefer ATS feeds where they exist (required where trivial):** many career pages are served by
  Greenhouse/Lever/Ashby, which expose clean JSON endpoints/APIs. Prefer those over HTML scraping
  when available — more reliable *and* friendlier. The `pipeline/source` abstraction lets each
  company resolve to "ATS feed if known, else scrape."
- **Provenance:** store `source_url` + `content_hash` for every posting (no raw-HTML object
  storage); fields are auditable via the source URL and re-fetch.
- **Removal path:** provide a per-company opt-out so a company can be excluded on request.
- **PII & data:** the only personal data is the user's own profile + their saved roles. Support
  **export** and **account deletion** (cascade deletes via FK). Encrypt secrets; never log raw API
  keys or full candidate profiles. GDPR-aligned (EU-centric user base).
- **LLM data:** send only posting text + the user's targeting/skills needed for scoring; use OpenAI
  with data-retention/zero-retention settings per the org's agreement; never send another user's data.

---

## 16. Observability, testing, CI/CD

- **Logging:** structured JSON (request id, user id, run id, stage). **Tracing:** OpenTelemetry across
  BFF→API→worker. **Errors:** Sentry on web and api.
- **Run dashboards:** surface `runs.stats` internally (found/new/closed/low-conf/errors) + LLM spend
  per run; alert on error-budget breaches and cost spikes.
- **Testing:**
  - *Backend:* unit tests for scoring (golden cases incl. the red-flag/low-overlap role), extraction
    schema validation, dedup clustering, lens→SQL filters; contract tests against OpenAPI.
  - *Pipeline:* fixture HTML → extraction snapshot tests (deterministic via recorded LLM responses).
  - *Web:* component tests; **Playwright E2E** for the four signature moments + core flows (open
    drawer morph, lens re-sort, approve→registry, status change persists across reload).
  - *Visual regression* against the prototype for pixel-faithfulness on key screens.
- **CI/CD (GitHub Actions):** lint/typecheck/test → generate TS types from OpenAPI → deploy web to
  **Vercel** and api/worker/scheduler to **Fly/Render**; run Alembic migrations as a release step;
  smoke test post-deploy.

---

## 17. Environments & configuration

- **Envs:** local (docker-compose: Postgres+pgvector, Redis, FastAPI, Next), preview
  (Vercel preview + an api preview), production.
- **Secrets:** `OPENAI_API_KEY`, `DATABASE_URL` (Neon pooled + direct), `REDIS_URL`,
  `AUTH_SECRET`/OAuth creds, `SERVICE_JWT_SECRET` (BFF↔API). Managed via Vercel
  env + the container host's secrets; never in the repo.
- **Config flags:** `SCORING_VERSION`, model tiers, crawl concurrency, run cadence.

---

## 18. Milestones / roadmap

> Each milestone is shippable and demoable. Frontend can develop against seeded/fixture data from M1
> while the pipeline lands in M3–M4.

- **M0 — Foundations.** Monorepo, CI, envs, Neon + migrations, Auth.js login, app shell + Sidebar +
  routing, Tailwind tokens, fonts. Empty routed views. *(Prototype §2, §6; this §10–11.)*
- **M1 — Design port (static data).** Port every view + the four signature moments pixel-faithfully
  against seeded data served by a stubbed API. Visual-regression vs prototype passes. *(§12–14.)*
- **M2 — Persistence & tenancy.** Real schema + RLS; CRUD for lenses/candidate/targeting/companies;
  posting state (status/note/feedback) persists; tweaks persist. Demo seeder. *(§4, §8, §9.)*
- **M3 — Discovery & approvals.** Crawl/fetch career pages → approval queue → approve→enrich→registry
  → fetch postings (content_hash change-detection). On-demand "Refresh now" only; sidebar sync +
  Refresh now wired to run status. *(§5, §7.)*
- **M4 — Extraction & scoring.** OpenAI structured-output extraction → insight records; embeddings;
  dedup; hybrid salary-blind scoring + rationale; low-confidence handling; Insights aggregates from
  real data. *(§5–6.)*

  > **Build note (M3+M4 shipped, `45dee7f`):** M3 and M4 were built as ONE manually-triggered
  > vertical slice — discovery → approval → enrich → crawl → extract → dedup → score → render — run
  > inline on demand. A later milestone owns **automation**: the weekly scheduler and its
  > background-worker/queue and hosting infra (§7). Status: `docs/M4-STATUS.md`.
- **M5 — Hardening.** Observability, rate limits, scraping politeness, export/delete; E2E + load
  test; cost controls. *(§15–16.)*
- **M6 — Polish & launch.** Keyboard nav/a11y pass, onboarding (collect starting companies), empty/
  loading states, perf budget, security review.

---

## 19. Definition of done (production acceptance)

**Design fidelity**
- [ ] Every view matches the prototype 1:1 (warm paper, Spectral/Geist Mono, layout, density,
      tweaks); visual-regression suite green.
- [ ] All four signature moments work in Next.js client components and respect reduced-motion.
- [ ] Counts (lens bar, "new", profiles) are **derived server-side**, never stored/hard-coded.
- [ ] Red-flag roles penalized & flagged; low-confidence "surfaced, not trusted" & excluded from
      Insights; **salary never ranks/filters** and is shown only when present.

**Product & platform**
- [ ] Multi-tenant isolation enforced by data-layer scoping **and** RLS; verified by tests (no user
      can read another's rows).
- [ ] A scheduled weekly run and an on-demand "Refresh now" both execute the full pipeline; sidebar
      reflects real run status; results appear without reload errors.
- [ ] Discovery → approval → registry → postings → extraction → scoring works end-to-end on real
      career pages for a seed set of companies.
- [ ] Scores are reproducible (`scoring_version` + `scored_with`); numbers are computed, rationale is
      generated.
- [ ] Auth, account bootstrap, data export, and account deletion (cascade) all work.
- [ ] Observability in place (logs/traces/errors + run & cost dashboards); CI deploys web→Vercel and
      api→container host with migrations; post-deploy smoke passes.
- [ ] Scraping respects robots.txt + rate limits; `source_url` + `content_hash` stored for
      provenance; per-company removal path exists.

---

## Appendix A — Open decisions to confirm
1. ~~Discovery seeding without a search API~~ — **RESOLVED:** use OpenAI's built-in `web_search`
   tool for discovery/seeding (domain-filtered to ATS hosts), with our own fetch/snapshot for
   ingestion (§5). Onboarding may also let users seed a few companies. The `pipeline/source`
   abstraction keeps official ATS feeds / alternate search providers swappable later.
2. ~~Scraping legal posture~~ — **RESOLVED:** scrape freely but politely (robots.txt, rate limits,
   descriptive UA, caching), and prefer ATS JSON feeds where available. Requirements live in §15;
   a per-company removal path is included.
3. **Worker stack** — Arq (async, lighter) vs Celery (mature, heavier). Spec defaults to Arq.
4. **Container host** — Fly.io (default) vs Railway/Render.
5. **Run cadence** — weekly-run staggering policy.
6. **Drawer routing** — intercepting route `/jobs/{id}` (shareable URL) vs pure client overlay; affects
   how morph rects are passed (§13).
