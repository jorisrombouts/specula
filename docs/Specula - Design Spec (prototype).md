# Specula — Design & Build Specification

> A reproduction spec for **Specula**, a personal "role ledger" — a job-discovery and
> application-tracking tool for one power user. This document is written so a coding
> agent can rebuild the product from scratch and arrive at the same design.
> Read it top to bottom; build in the order of §11.

---

## 0. Concept & positioning

Specula is **not** a job board and **not** a CRM. It is a single user's private instrument
for tracking a curated, deduplicated pool of roles, scored against *who they are* and *what
they want*. The emotional register is an **editorial instrument** — a broadsheet newspaper
crossed with a financial terminal. Warm paper, serif display headlines, monospace numerics.
Calm and authoritative, never "SaaS-y."

The product must feel like a **considered object**, not a dashboard. Four moments carry the
"wow" (specified in detail in §9): an assembling intro, an animated lens re-sort, a
match-score "scoring" reveal, and a row→drawer shared-element morph. Everything else is quiet
so those moments land.

**Primary user (persona for seed data):** Joris Veldkamp — a remote-EU-first Data Scientist /
ML Engineer, 6 yrs, Amsterdam, targeting applied-LLM / agentic-systems roles.

---

## 1. Tech stack & architecture

- **Single-page app, no build step.** Plain HTML entry file + React 18 via UMD + Babel
  Standalone for in-browser JSX. (If your agent prefers a bundler/Vite + TSX, that's fine —
  the *design* is what matters, not the loader. Keep it a client-only SPA; there is no backend
  in this prototype — all data is in-memory seed data.)
- **React 18**, function components + hooks only. No router library — view state is a single
  `useState` string ("jobs", "companies", …).
- **Styling: hand-written CSS with CSS custom properties** (design tokens). No Tailwind, no
  CSS-in-JS. Two stylesheets: a design-system sheet and a view sheet.
- **Motion:** CSS keyframes/transitions for entrances; the **Web Animations API**
  (`element.animate(...)`) for the FLIP re-sort; `requestAnimationFrame` for count-ups.
- **Fonts (Google Fonts):** Spectral (display, 400–700), Hanken Grotesk (body, 400–700),
  Geist Mono (mono, 400–600). Also load Newsreader and Source Serif 4 — they are selectable
  display fonts via the Tweaks panel.

### File structure
```
Specula.html              # entry: loads fonts, CSS, then scripts in order
specula/
  specula.css             # design system: tokens, app shell, sidebar, shared atoms, intro
  views.css               # per-view styles: job rows, lens bar, drawer, tables, panels, forms
  data.jsx                # all seed data + the lens-filter function (window.SPECULA)
  ui.jsx                  # shared components: MatchMeter, OverlapBar, Icon, useCountUp
  jobs.jsx                # JobsView + Drawer + FLIP re-sort (the core)
  pipeline.jsx            # ApprovalsView + CompaniesView
  intel.jsx               # InsightsView (market intelligence)
  config.jsx              # ProfilesView + CandidateView + TargetingView + TagEditor
  intro.jsx               # IntroOverlay (assembling intro)
  app.jsx                 # App shell: Sidebar, routing, tweaks wiring, mounts React root
  tweaks-panel.jsx        # in-design tweak controls (host-provided component)
```
Scripts load in dependency order: `tweaks-panel → data → ui → jobs → pipeline → intel →
config → intro → app`. Components communicate by attaching to `window` (since each Babel
script has its own scope). In a bundler setup, use normal imports instead.

---

## 2. Design system — tokens

All colors are warm (paper, not white). Define as CSS custom properties on `:root`.

| Token | Value | Use |
|---|---|---|
| `--paper` | `#FBFAF6` | page background |
| `--panel` | `#F4F2EB` | sidebar, hover fills |
| `--panel-2` | `#EEEBE1` | bar tracks, logos, deeper fills |
| `--card` | `#FFFFFF` | cards, inputs, table-row pop |
| `--ink` | `#211E18` | primary text, active fills (near-black, warm) |
| `--ink-2` | `#7C7567` | secondary text |
| `--ink-3` | `#ABA493` | tertiary / captions |
| `--rule` | `#E4E0D5` | hairline dividers |
| `--rule-2` | `#D6D1C2` | stronger borders |
| `--accent` | `#2E7D4F` | green — high match, positive, primary accent |
| `--accent-bg` | `#E7F0E9` | accent tint background |
| `--accent-ink` | `#1E5D39` | accent text on tint |
| `--warn` | `#B3541E` | burnt orange — red flags, deadlines, gaps, negatives |
| `--warn-bg` | `#F7EBE0` | warn tint background |
| `--gold` | `#9A7A18` | secondary data series |

**Shadows:** `--shadow-card: 0 1px 2px rgba(33,30,24,.04)`;
`--shadow-pop: 0 16px 50px -12px rgba(33,30,24,.28), 0 2px 8px rgba(33,30,24,.08)` (drawer).

**Typography**
- Display: `--font-display: 'Spectral', serif` — view titles (34px/600), job titles
  (20px/600), drawer title (25px), panel titles (17px). Tight tracking `-.01em`.
- Body: `--font-body: 'Hanken Grotesk', sans-serif` — 14px base, line-height 1.5.
- Mono: `--font-mono: 'Geist Mono', monospace` — all numerics, labels, metadata, kickers,
  column headers. Uppercase mono labels use `letter-spacing: .08–.16em`.
- Base font-size 14px; `-webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility`.
- Use `text-wrap: pretty` on multi-line prose (rationales, summaries).

**Density** (driven by `data-density` on `<html>`):
- comfortable (default): `--row-py:17px; --gutter:34px; --card-pad:20px`
- compact: `--row-py:11px; --gutter:26px; --card-pad:15px`, and **hide job-row rationale**,
  shrink job titles to 18px.

**Layout shell:** `.app { display:grid; grid-template-columns:236px 1fr; height:100vh;
overflow:hidden }`. Sidebar fixed-width, main column scrolls. Views are centered with
`max-width:1180px; margin:0 auto; padding:30px var(--gutter) 64px`.

---

## 3. Component atoms (shared vocabulary)

- **View header** (`.vhead`): flex row, `border-bottom:1.5px solid var(--ink)`. Left: serif
  `.vtitle` + a `.vsub` one-paragraph explainer (≤64ch, `--ink-2`). Right: `.vhead-stat` —
  mono figures with bold values and thin vertical separators.
- **Chips** (`.chip`): 11.5px, hairline border, paper bg, 6px radius. `.chip-mono` for numerics.
- **Tags:** `.tag-new` (green dot + "NEW" mono), `.tag-status` (outlined uppercase mono),
  `.tag-flag` (warn-colored, prefixed with `⚑` or `⚐`).
- **Buttons:** `.btn` (hairline, hover → ink border), `.btn-pri` (ink fill), `.btn-accent`
  (green fill), `.btn-ghost`. 7px radius, 12.5px/500.
- **Toggle** (`.toggle`): 38×22 pill switch, `--rule-2` off → `--accent` on, sliding knob.
- **Icons:** a tiny inline-SVG set drawn from single `<path>` strings (`stroke:currentColor;
  stroke-width:1.4; fill:none; round caps`). 16px viewBox. Keys: jobs, approvals, companies,
  insights, profiles, candidate, targeting. Geometric/utilitarian — no filled or decorative icons.

---

## 4. Data model (in-memory; `window.SPECULA`)

All data lives in one object. Shapes below are the contract; values are illustrative.

### 4.1 `candidate` — who I am (drives scoring + skills-gap)
```js
{ name, initials, title, location, workMode, visa, years, education,
  languages: [str], skills: [str],
  projects: [{ name, note }],
  experience: [{ role, org, period }] }
```

### 4.2 `targeting` — global baseline (what I want; shared across all lenses)
```js
{ roleTitles: [str],     // synonyms — the field has many names for the same role
  seniority: [str], mustHaves: [str], avoid: [str],
  preferences: str }     // free-text soft signal
```
**Hard rule:** salary is *never* a targeting field or scoring signal. It is only extracted
and displayed when an ad states it. Call this out in the Targeting UI.

### 4.3 `lenses` — named search profiles (a saved view over the one shared pool)
```js
{ id, name, short, active: bool,
  scope: str,            // hard: location scope (e.g. "EU", "ES", "Berlin, DE")
  modes: [str],          // hard: allowed work modes
  origin: str,           // hard: HQ rule (e.g. "Only foreign HQ", "Any HQ")
  focus: str,            // soft signal, free text
  count, isNew,          // display only — real counts are derived (see §4.6)
  seeds: [str] }         // auto-generated discovery queries
```
First lens is always `all` (no filters). A role can belong to several lenses at once.

### 4.4 `jobs` — the shared, deduped pool (each carries a full "insight record")
```js
{ id, company, logo, title,
  city, country, hq,            // country = where the job is; hq = company HQ country
  mode,                          // "Remote" | "Hybrid" | "On-site"
  flag,                          // emoji flag of job location
  match,                         // 0–100 overall index
  factors: { role, skill, loc }, // 0–100 each — the three sub-scores shown as bars
  overlap: [matched, total],     // required-skill overlap, e.g. [8, 9]
  seniority, edu, deadlineDays, salary|null, posted,
  status: null|"Saved"|"Applied"|"Interviewing"|"Offer"|"Dismissed",
  isNew, stillOpen, originVerified, hqConf,   // hqConf 0–100
  redFlag?: str,                 // e.g. "Low required-skill overlap" (one-way penalty)
  stack: [str], niceToHave: [str],
  visa, langs: [str], contract, geo, confidence,  // confidence = extraction confidence 0–100
  responsibilities: [str],
  summary: str,                  // 1–2 sentence human summary
  rationale: str }               // WHY this scored as it did — shown on the row
```
Seed ~13 roles spanning: a top match (94), a saved one, an applied one, a **red-flag**
low-overlap role (match ~71, `factors.skill` ~41, `redFlag` set, `originVerified:false`),
a dismissed one, plus Berlin/Spain/remote variety so every lens is populated. Use real-sounding
EU AI companies (Mistral AI, Aleph Alpha, DeepL, Helsing, ElevenLabs, Qonto, Synthesia, Parloa…).

### 4.5 `companies`, `approvals`, `insights`, `skillsGap`
- `companies`: registry rows `{ name, logo, domain, ats, hq, flag, conf, open, comp, added, unverified? }`.
  `conf` is HQ-origin confidence 0–100 (<80 renders in warn). `comp` is a coarse "€€/€€€" estimate.
- `approvals`: candidate companies awaiting a decision
  `{ id, name, logo, domain, ats, hq, flag, query, why, roles, unverified? }`. `query` is the
  discovery search that surfaced it; `why` is the rationale.
- `insights`: aggregates — `skillDemand:[{skill,pct,delta,up,gap?}]`,
  `trend:{weeks:[…], series:[{name,color,data:[…]}]}` (stacked weekly),
  `seniorityMix`, `modeMix`, `salary:[{band,lo,hi}]`, `activeCompanies`, plus
  `totalAnalysed` and `lowConfExcluded` counts.
- `skillsGap`: `[{ skill, roles, note }]` — most-demanded skills across target roles that are
  absent from the candidate profile.

### 4.6 Derived: lens filtering (single source of truth)
```js
SPECULA.filterByLens(jobs, lensId) →
  all      : every non-dismissed role
  remote   : mode === "Remote"
  foreign  : hq !== country            // company HQ differs from job's country
  spain    : country === "ES"
  berlin   : city === "Berlin"
```
**Every count in the UI is derived by calling this** (lens-bar counts, "N new" badges,
Profiles card counts). Never hard-code counts — they must stay honest as data changes.

---

## 5. The signature component — `MatchMeter`

The match score is the hero element; it has **three visual styles** (Tweak-selectable) and
**three behavior modes**. One component, props-driven.

**Styles** (`mstyle`):
- `bars` (default) — the overall number (mono, 36px, colored) + "/100" + a right-aligned mono
  label, above three labeled tracks (ROLE / SKILL / LOC) that fill to their factor %.
- `figure` — just the big number at 54px, no bars.
- `ring` — a conic-gradient ring (`conic-gradient(color Xdeg, track 0)`) with the number
  centered, plus a compact `R·96 S·89 L·92` factor list beside it.

**Color logic** (`matchColor`): `redFlag` → `--warn`; `match ≥ 85` → `--accent`; else `--ink`.
Any individual factor `< 50` renders that bar in `--warn` regardless.

**Behavior modes** (props):
- `replay` — a key/value that, when it changes, re-runs the fill sweep from 0. Used by the
  lens re-sort so meters visibly re-score.
- `countUp` — count the number up from 0 (used on rows as they enter).
- `reveal` — the drawer "scoring" mode: starts at 0 with the label reading **"scoring…"**,
  waits ~320ms, sweeps the bars up and counts the number up over ~780ms, then swaps the label
  to **"match index"**. This makes the verdict feel *computed*, not displayed.

Other shared components: `OverlapBar` (inline `[8/9] req. skills` with a mini fill bar; turns
warn when overlap ratio < 0.4), `Icon`, and `useCountUp(target, run, duration)` (rAF cubic
ease-out integer count-up).

---

## 6. App shell

- **Sidebar** (`.side`, 236px): brand lockup ("Specula" serif + "role ledger" mono kicker);
  a sync row with a pulsing accent dot ("synced 2d ago · 11 new") and a "Refresh now" button
  (spins its ↻ glyph for ~1.4s on click, then sets "just now"); nav grouped under mono section
  labels **Pipeline / Intelligence / Configure**; a pinned candidate card at the bottom that
  opens the Candidate view. Active nav item = ink fill, paper text. Approval queue shows a
  warn-colored count badge.
- **Routing:** `view` state string selects from a `views` map. `<main key={view}>` so each
  view remounts and replays its entrance animation. Main column owns the scroll.
- Nav order: Jobs, Approval queue, Companies | Insights | Search profiles, Targeting (+ Candidate
  via the bottom card).

---

## 7. View specifications

### 7.1 Jobs (the core)
- View header (pool count + new count). Then the **lens bar**: a horizontal segmented control,
  one cell per lens, each showing name (+ green dot if it has new roles) and a mono
  "N roles · M new" line; active cell = ink fill. Counts are derived per §4.6.
- A **deadline banner** (warn tint) appears when ≥1 role in the lens closes within 7 days.
- A toolbar line echoes the active lens's hard rules (scope · modes · origin) and a sort
  `<select>` (match ↓ / deadline ↑ / newest).
- A mono **column header** (`# · role/source/facts · match · role/skill/loc`).
- **Job rows** (`.jrow`, 3-col grid: index / body / meter):
  - index (mono, zero-padded), then body: title (serif) + NEW/status tags; a mono meta line
    (`company / 🏳 city / mode / seniority / salary`) with `/` separators; the **rationale**
    paragraph (the "why"); a mono footer (`OverlapBar · top-5 stack · ↳ closes Nd · ⚑ redflag ·
    ⚐ origin unverified`). On the right, the `MatchMeter`.
  - Hover: a soft `--panel` fill slides in behind the row (`::before`, inset −14px, radius 8).
  - Entrance: rows stagger in (`rowIn`, translateX + fade, 45ms × index).
  - Click → opens the **Drawer**.
  - Layout Tweak `cards`: switch `.jlist` to a 2-col grid of bordered cards; meter moves below
    the body under a dashed divider; hide index and column header.
- **Lens re-sort:** see §9.2 (the centerpiece).

### 7.2 Job detail Drawer
Right-side panel (560px, `--shadow-pop`), scrim with blur. When opened **from a job row** it
arrives via the shared-element morph (§9.4); when opened by other means (e.g. keyboard) it
slides in via `translateX` and plays the scoring reveal. Sticky header (company kicker, serif
title, sub-meta, close ✕). Body sections, each under a
mono `.dr-sec-h` divider label:
1. **Match** — `MatchMeter` (in `reveal` mode — the scoring reveal, §9.3 — only when *not*
   morphing; when morphing it shows the final value, since the number travelled in from the
   row) + rationale + overlap + deadline.
2. **Summary** — the human summary paragraph.
3. **Skills · required vs your profile** — `have ✓` chips (accent tint) and `missing +` chips
   (warn, dashed). Note that gaps feed the skills-gap view.
4. **Insight record** — a `<dl>` key/value dump of the extracted fields (role family, seniority,
   mode, geo, visa, languages, salary or "not stated", contract, deadline, posted, still-open),
   ending with **extraction confidence** (renders warn + "surfaced, not trusted" if < 75%).
5. **Responsibilities** — bullet list.
6. **Application status** — a 4-step lifecycle (Saved → Applied → Interviewing → Offer) where
   clicking a step sets status; completed steps get accent dots; plus a free-text note field.
7. **Feedback** — "↑ Good match" / "↓ Not for me". Choosing "not for me" reveals dismissal
   reason chips (Too junior / Wrong location / Comp / Stack mismatch / Not my field); picking one
   animates the row out of the pool and logs the negative signal. "Good match" logs a positive
   example (and saves the role).
8. Footer actions: Open posting / Save.

### 7.3 Approval queue
A 2-col grid of company cards: logo, name+flag, domain, "N open" chip, the **why** rationale,
ATS chip + HQ chip (or `⚐ HQ origin unverified` when flagged), and a mono `⌕ found via "query"`
line. Actions: **Approve** (accent) / **Reject** / **Snooze** (☾). On a decision the card scales
+ fades out and the header tallies update. Empty state summarizes the session's decisions.
Copy must explain: approving enriches the company (HQ + confidence, comp estimate) and adds it
to the registry; rejecting suppresses repeats.

### 7.4 Companies registry
A filter input (by name/HQ) + a table: Company (logo + domain), ATS feed chip, HQ country
(flag), **HQ confidence** (mini bar + %, warn + ⚐ when < 80), Open count, Comp estimate chip,
and a tracking Toggle per row. Global across all lenses.

### 7.5 Insights (personal market intelligence)
A header with a period `<select>` and an animated `analysed` count-up. A standing note that N
low-confidence extractions are excluded. Then a 2-col panel grid:
- **Skill demand** — horizontal bars (% of postings) with ▲/▼ deltas; skills missing from the
  profile get a "gap" flag.
- **Demand drift** — a stacked weekly bar chart (3 series) built from CSS-height divs + a legend.
- **Seniority mix**, **Work-mode mix** (a single segmented `flex` bar + drift note), **Salary
  distribution** (range bars; reiterate "informational only, never used to rank"), **Most-active
  companies**. All bars/counts animate from 0 on mount.

### 7.6 Search profiles (lens editor)
Header (active/total counts). One card per lens (except `all`): name + derived count + an
active Toggle; a 3-col grid of **hard rules** (Location scope / Work mode / Origin rule) and
below, the **soft focus** signal + the auto-generated **discovery seeds** chips. Inactive lenses
dim. "+ New profile" button. Make the baseline-vs-delta model explicit in the `.vsub`.

### 7.7 Candidate profile
A 2-col form: left = editable headline, location, work mode, years, visa, a **skills tag editor**
(add/remove chips), projects, experience, education & languages. Right = a sticky **skills-gap
panel** listing the most-demanded missing skills with little bar glyphs and an "N×" count, plus a
"Draft a tailored CV bullet" button. Frame it as an explicit form (not a parsed CV) the user controls.

### 7.8 Targeting
A single column: role-title **synonym** tag editor (chips styled as `syn` = ink fill), seniority
chips, side-by-side Must-haves / **Avoid** (avoid chips in warn) editors, and a free-text
preferences textarea. End with an accent-tinted note restating the **no-salary-signal** rule.

`TagEditor` is a shared control: renders removable chips + an inline "+ add" that becomes a text
input (commit on Enter/blur). Variants via a `kind` prop (`syn`, `avoid`).

---

## 8. Tweaks panel

An in-design control panel (toggleable). Exposes, with sensible defaults persisted:
- **Match score** style: bars / figure / ring (default bars)
- **Job layout**: rows / cards (default rows)
- **Display font**: Spectral / Newsreader / Source Serif 4
- **Accent** color: `#2E7D4F` / `#2D5BBF` / `#9A7A18` / `#7A4FB0` (swatches)
- **Spacing** density: comfortable / compact

Apply by writing CSS variables / `data-*` attributes on `<html>`:
`--accent` (+ derive `--accent-bg` and `--accent-ink` via `color-mix`), `--font-display`,
`data-density`, `data-layout`. Everything else reacts through the cascade.

---

## 9. The three signature moments (build these with care)

### 9.1 Assembling intro (`IntroOverlay`)
A full-screen paper overlay, **~2s**, **skippable** (click or any key), shown **once per tab
session** (guard with `sessionStorage`). Sequence: the wordmark "Specula" rises out of a blurred,
letter-spaced state into place (serif, 86px); a hairline rule draws across horizontally; the mono
tagline fades in; five ledger lines draw in left-to-right (staggered `scaleX`); a mono stat line
ticks up a role count (count-up to 47). On finish (timeout or input) the **entire sheet lifts up**
(`translateY(-101%)`, ~640ms) to reveal the app beneath. Under `prefers-reduced-motion: reduce`,
collapse to a ~250ms near-instant version. Provide an optional "replay intro" affordance.

### 9.2 Animated lens re-sort (the centerpiece) — FLIP
Switching a lens (or sort) must make the pool **physically rebuild**, not snap-filter:
- Use **FLIP** (First-Last-Invert-Play). Keep a ref of each row's `{top,left,width}` keyed by job
  id (measured in `useLayoutEffect`). On change: measure new positions; for every surviving row,
  `element.animate([{transform: translate(Δx,Δy)}, {transform:'none'}], {duration:560, easing:
  'cubic-bezier(.3,.9,.3,1)'})` so it flies from old slot to new.
- Rows that **leave** the lens render as absolutely-positioned **exit clones** at their old
  position and fade/slide out (`rowExit`, ~460ms) — so departures are visible, not instant.
- Rows that **enter** stagger in via the normal entrance.
- Every visible `MatchMeter` **re-sweeps** (driven by a `replay` key = `lens|sort`), so it reads
  as "re-scored for this lens."
- The `.jlist` is `position:relative` to anchor the exit clones. Respect reduced-motion (skip the
  FLIP transforms, just re-render).
- **Acceptance:** switching to "Foreign HQ" leaves exactly the foreign-HQ roles in correct ranked
  order while the others animate away; no layout jump; no console errors.

### 9.3 Match scoring reveal
Opening the drawer renders its `MatchMeter` in `reveal` mode: number starts at 0, label reads
**"scoring…"**, a beat (~320ms) passes, then bars sweep up and the number counts up (~780ms)
before the label settles to **"match index"**. The verdict should feel earned.

> Note: when the drawer is opened by **clicking a row**, the scoring reveal is *suppressed* and
> the meter shows its final value immediately — because the number visually travelled in from the
> row (§9.4). The reveal is for entries that have no source row (keyboard / command palette).

### 9.4 Row → drawer shared-element morph
Clicking a job row must make the row and the drawer feel like **one continuous object**, not a
panel sliding over a list. Technique (FLIP on real drawer elements):
- **Capture (in the row, on click):** read viewport rects of the row's `.jtitle` and `.meter`
  via `getBoundingClientRect()`, plus the title's computed `font-size`. Pass this `morphFrom`
  payload up alongside the selected job.
- **Play (in the drawer, on mount, `useLayoutEffect`):** measure each destination element's rect,
  then `element.animate()` it **from** `translate(Δx,Δy) scale(s)` (origin `left top`, opacity
  ~0.55) **to** identity, ~540ms `cubic-bezier(.4,0,.12,1)`, `fill:"backwards"`.
  - **Title** scale = `srcFontSize / destFontSize` (font-ratio, *not* box-ratio — the drawer
    title is a full-width block, so a box-width scale would squash it). The row title grows into
    the drawer title.
  - **Meter** scale = `srcWidth / destWidth` (both are `.meter`, ~228px, so ~1× — it mainly
    translates from the row's right column into the drawer's match section). Wrap the drawer
    `MatchMeter` in a `ref`'d div with `transform-origin:left top` so it can be transformed.
  - Clamp scale to `[0.3, 1.4]` for safety.
- **Supporting content:** the panel does a quick opacity fade (~240ms, **no transform** — a parent
  transform would compound with the children's morph). The kicker, sub-meta, body sections
  (skip the morphing meter's section[0]) and footer rise in with a small staggered fade-up.
- **Scrim** fades in (~300ms).
- **Close:** panel slides out `translateX(46px)` + fades (~300ms) and scrim fades; unmount on the
  animation's `onfinish` **with a `setTimeout` fallback** (so a throttled tab can't strand the
  drawer open). No reverse-morph (robust against the source row having scrolled/changed).
- **Reduced motion:** skip all of the above; the drawer simply appears at rest.
- **Acceptance:** the clicked row's title and match number visibly fly into the drawer header and
  settle into place; no console errors; closing animates out and fully unmounts.

---

## 10. Motion & accessibility principles

- Entrances: short (0.4–0.6s), `cubic-bezier(.2,.7,.2,1)`, translate+fade, staggered by index.
- Bars/rings: width/gradient transitions ~0.8–0.9s, `cubic-bezier(.3,1,.3,1)`.
- Count-ups: rAF, cubic ease-out, integer steps.
- **No infinite decorative loops** on content. The only persistent motion is the small sync-dot
  pulse in the sidebar.
- Honor `prefers-reduced-motion: reduce` for the intro, the FLIP, and entrances.
- Desktop-first dense tool (it is an instrument, not a marketing page). Min text 11px, but
  numerics/labels in mono carry most small sizes. Maintain AA contrast on `--ink-2`/paper.

---

## 11. Build order (recommended)

1. Tokens + app shell + sidebar + empty routed views (§2, §6).
2. Seed data + `filterByLens` (§4).
3. `MatchMeter` (all 3 styles, static first) + `OverlapBar` + `useCountUp` (§5).
4. Jobs view: rows, lens bar with derived counts, sort, deadline banner (§7.1).
5. Drawer with all sections (§7.2), then add the scoring reveal (§9.3) and the row→drawer morph (§9.4).
6. Approvals, Companies, Insights, Profiles, Candidate, Targeting (§7.3–7.8).
7. Tweaks panel wiring (§8).
8. The FLIP lens re-sort (§9.2).
9. The assembling intro (§9.1).
10. Reduced-motion passes + final polish (§10).

## 12. Definition of done (acceptance checklist)
- [ ] Warm-paper editorial look; Spectral display, mono numerics throughout; no pure-white, no
      generic SaaS chrome.
- [ ] All lens counts, "new" badges, and Profiles counts are **derived**, never hard-coded.
- [ ] Switching a lens triggers the FLIP re-sort (survivors fly, leavers fade, meters re-sweep).
- [ ] Opening a role plays the scoring reveal (0 → value, "scoring…" → "match index").
- [ ] Clicking a row morphs its title + meter into the drawer header (shared-element §9.4); the
      drawer closes with an animated slide-out and fully unmounts.
- [ ] The intro plays once per session, is skippable, and collapses under reduced-motion.
- [ ] Red-flag role visibly penalized (warn color, ⚑, low skill factor); unverified origin flagged.
- [ ] Salary never used to rank/filter; shown only when present; stated explicitly in Targeting.
- [ ] All five Tweaks work live via CSS variables / data-attributes.
- [ ] No console errors; main column scrolls; sidebar fixed; drawer overlays correctly.
