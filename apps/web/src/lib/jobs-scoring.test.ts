import { describe, it, expect } from "vitest";
import { scoredList } from "@/lib/jobs-scoring";
import { jobs as seedJobs } from "@/lib/seed/data";

// M2: `getJobs` (lib/api/jobs.ts) now forwards FastAPI's own server-computed
// scoring instead of calling `scoredList`, so this no longer asserts
// equivalence with the route (that invariant only held while both sides ran
// the same TS function — see the M2 frontend-wiring report). `scoredList` is
// still exercised directly here, against the seed pool, since the client
// (JobsView) keeps using it to re-derive its own per-lens ranking.
describe("scoredList", () => {
  it("re-scores per lens (foreign changes loc/match vs all)", () => {
    const all = scoredList(seedJobs, "all", "match");
    const foreign = scoredList(seedJobs, "foreign", "match");
    expect(foreign.length).toBeLessThan(all.length);
  });

  it("sorts by match descending for the default lens", () => {
    const all = scoredList(seedJobs, "all", "match");
    expect(all.every((j, i) => i === 0 || all[i - 1].match >= j.match)).toBe(
      true,
    );
  });
});
