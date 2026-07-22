# M5 Lane DATA — Data export + account-deletion cascade + per-company opt-out

Read `m5-fanout-playbook.md` first. Branch `m5-data`, DB `specula_wt_data`. Size: **M**.

## Purpose
GDPR data export of the user's own data; account deletion via FK cascade; the per-company
removal/opt-out path (spec §15).

## Files you own (touch ONLY these)
- `apps/api/specula_api/routers/account.py` — fill the foundation stub: `GET /account/export`
  (returns `ExportBundle`), `DELETE /account` (deletes the account).
- Create `apps/api/specula_api/services/account.py`:
  - **Export**: gather all per-user tables under `async with tenant_session(user_id)` (RLS
    auto-scopes reads) into the frozen `ExportBundle` shape. **Exclude `skills_taxonomy`**
    (global/unscoped). **Include `llm_costs`.**
  - **Delete**: `DELETE FROM users WHERE id = :uid` — every tenant table's `user_id` FK is
    `ON DELETE CASCADE`, so this removes all the user's rows (incl. `llm_costs`). Excludes
    global `skills_taxonomy` by construction.
- Create `apps/api/specula_api/schemas/account.py` — Pydantic models serializing to the
  frozen `ExportBundle` camelCase shape (clone the `CamelModel` pattern from
  `schemas/targeting.py`).
- `apps/api/specula_api/routers/company.py` — add the opt-out endpoint (e.g.
  `POST /companies/{id}/opt-out`) toggling `companies.opt_out`; an opted-out company is
  excluded from future ingest. (No other lane touches `company.py`.)
- Web slice: `apps/web/src/app/(app)/settings/page.tsx` (route already in nav),
  `apps/web/src/components/settings/`, `apps/web/src/app/api/account/route.ts` (+
  `export/route.ts`), `apps/web/src/lib/api/account.ts`. Export = download; delete =
  confirm-then-`DELETE`.

## Tests (tenancy is critical here)
- Export contains the caller's rows and serializes to `ExportBundle` (camelCase); a second
  user's export is disjoint.
- **Cross-tenant cascade**: delete user A → A's rows gone from EVERY per-user table
  (`companies`, `postings`, `scores`, `runs`, `llm_costs`, …); **user B intact**.
- `skills_taxonomy` untouched by both export and delete.
- Opt-out: toggling `opt_out=true` excludes the company from the next ingest.

## Out of scope (binary)
No cost/logging (OBS). No rate limiting (NET). No dashboard (DASH). No
`shared-types`/migration/`config.py`/`routers/__init__.py`/`nav.ts` edits (foundation).
