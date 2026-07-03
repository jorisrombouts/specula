import { describe, it, expect } from "vitest";
import { scoredList } from "@/lib/jobs-scoring";
import { getJobsPool, getJobs } from "@/lib/api/jobs";

describe("scoredList", () => {
  it("matches getJobs' orchestration (single source of truth)", () => {
    const pool = getJobsPool();
    for (const lens of ["all", "remote", "foreign"] as const) {
      const direct = scoredList(pool, lens, "match").map((j) => [
        j.id,
        j.match,
      ]);
      const viaRoute = getJobs(lens, "match").jobs.map((j) => [j.id, j.match]);
      expect(direct).toEqual(viaRoute);
    }
  });
  it("re-scores per lens (foreign changes loc/match vs all)", () => {
    const pool = getJobsPool();
    const all = scoredList(pool, "all", "match");
    const foreign = scoredList(pool, "foreign", "match");
    expect(foreign.length).toBeLessThan(all.length);
  });
});
