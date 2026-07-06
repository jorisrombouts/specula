# M2 Fan-out Lane: approvals

**Read `m2-fanout-playbook.md` first.**

**Endpoints:** `GET /approvals`, `POST /approvals/{id}/decision`.
**Models:** `Approval` (`db/models/approval.py`), and `Company` (approve → add to registry).
**Contract:** match `Approval` in `packages/shared-types/src/index.ts`.
**FE provider:** `apps/web/src/lib/api/approvals.ts` (`getApprovals`), consumed by
`approvals-view.tsx`/`approval-card.tsx` — wire the Approve/Reject/Snooze buttons
(currently inert) to `POST /approvals/{id}/decision`. Header "N approved" is DERIVED.

**Specifics:**
- `GET /approvals` returns the user's undecided queue (`decision IS NULL` — the partial
  index supports this).
- `POST /approvals/{id}/decision` body `{decision: "approve"|"reject"|"snooze"}` persists
  the decision. On **approve**, ALSO insert a `Company` row for that approval (name/domain/
  logo_url/ats/hq_country from the approval) — respecting `unique(user_id, domain)`.
  **Enrichment (HQ confidence, comp estimate, real crawl) is M3 — do NOT build it.** In M2
  just copy the approval's known fields into the company. Note this boundary in your report.
- The "approved" count shown in the UI is derived (companies added / approvals decided),
  never a stored counter.

**Tests:** list undecided, approve → creates a company + removes from undecided list,
reject/snooze persist, cross-tenant isolation.
