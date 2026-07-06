# M2 Fan-out Lane: companies

**Read `m2-fanout-playbook.md` first.**

**Endpoints:** `GET /companies`, `PATCH /companies/{id}`.
**Model:** `Company` (`db/models/company.py`) — 1:N, `unique(user_id, domain)`.
**Contract:** match `Company` in `packages/shared-types/src/index.ts` (name, logo,
domain, ats, hq, flag, conf, open, comp, added; note the TS uses short keys like `hq`/
`conf`/`comp` — map DB `hq_country`/`hq_confidence`/`comp_estimate` to them in the schema).
**FE provider:** `apps/web/src/lib/api/companies.ts` (`getCompanies`), consumed by
`companies-view.tsx` — wire the per-row tracking `Toggle` (currently a no-op) to
`PATCH /companies/{id}` (`tracking`). The search box stays client-side.

**Specifics:**
- `GET` lists the user's companies (seeded). `PATCH` partial-updates editable fields —
  primarily `tracking` (bool toggle), also name/ats/hq_country/comp_estimate/status.
- No `open`/count column is stored — if the TS `open` (open roles) is shown, derive it
  from postings for that company, don't persist a counter. (For M2 you may return the
  seeded value if a derivation source isn't wired; note it in your report.)
- Respect `unique(user_id, domain)` — surface a 409 on a conflicting domain edit.

**Tests:** list, PATCH tracking toggle persists, cross-tenant isolation.
