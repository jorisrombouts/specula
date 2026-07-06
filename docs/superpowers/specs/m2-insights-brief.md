# M2 Fan-out Lane: insights + skills-gap

**Read `m2-fanout-playbook.md` first.** This lane is read-only aggregates (no mutations)
over the seeded pool.

**Endpoints:** `GET /insights?period={4w|8w|q}`, `GET /skills-gap`.
**Models:** read-model over `Posting` + `Score` (+ `Targeting`/`CandidateProfile` for the
gap). No new tables.
**Contract:** match `Insights`, `SkillDemand`, `Trend`, `SeniorityMix`, `ModeMix`,
`SalaryBand`, `ActiveCompany`, `SkillsGap` in `packages/shared-types/src/index.ts`.
**FE providers:** `apps/web/src/lib/api/insights.ts` + `skills-gap.ts`, consumed by
`insights-view.tsx` + the candidate skills-gap panel.

**Specifics:**
- **`GET /insights`** computes aggregates from the user's postings within the period:
  skill demand, seniority/mode mix, salary bands (display-only — salary NEVER ranks),
  active companies, trends. **CRITICAL INVARIANT: exclude low-confidence postings** from
  every aggregate (`extraction_confidence` below the threshold — the seed includes one at
  42 specifically to test this). Everything is DERIVED; nothing is a stored count.
- **`GET /skills-gap`** derives missing skills: required_skills across the user's target
  roles (from `targeting`/postings) minus the candidate's `skills`. Port the shape from
  `apps/web/src/lib/seed/logic.ts` if a helper exists.
- `period` maps to a `posted_at`/`first_seen_at` window (4 weeks / 8 weeks / quarter).

**Tests:** aggregate correctness on seeded data, **low-confidence posting is excluded**
(assert the count changes when you flip the threshold), cross-tenant isolation.
