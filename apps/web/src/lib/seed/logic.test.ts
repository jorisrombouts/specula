import { describe, it, expect } from "vitest";
import { jobs, lenses } from "@/lib/seed/data";
import {
  filterByLens,
  scoreForLens,
  deriveLensSummaries,
  sortJobs,
} from "@/lib/seed/logic";

describe("filterByLens", () => {
  it("all → every job", () => {
    expect(filterByLens(jobs, "all")).toHaveLength(13);
  });
  it("spain → only ES jobs", () => {
    expect(
      filterByLens(jobs, "spain")
        .map((j) => j.id)
        .sort(),
    ).toEqual(["j13", "j7"]);
  });
  it("berlin → only Berlin jobs", () => {
    expect(
      filterByLens(jobs, "berlin")
        .map((j) => j.id)
        .sort(),
    ).toEqual(["j11", "j12"]);
  });
  it("foreign → hq != country", () => {
    expect(
      filterByLens(jobs, "foreign")
        .map((j) => j.id)
        .sort(),
    ).toEqual(["j3", "j4", "j5", "j7", "j8"]);
  });
});

describe("scoreForLens", () => {
  it("keeps role/skill lens-independent and recomputes loc+match per lens", () => {
    const j1 = jobs.find((j) => j.id === "j1")!;
    const all = scoreForLens(j1, "all");
    const remote = scoreForLens(j1, "remote");
    expect(all.factors.role).toBe(remote.factors.role); // 96
    expect(all.factors.skill).toBe(remote.factors.skill); // 89
    expect(remote.factors.loc).not.toBe(all.factors.loc); // loc changes
    expect(remote.match).toBe(87); // 0.4*96 + 0.4*89 + 0.2*64
  });
  it("caps match and flags when skill < 45", () => {
    const j5 = jobs.find((j) => j.id === "j5")!; // Sereact, skill 41
    const s = scoreForLens(j5, "remote");
    expect(s.redFlag).toBeTruthy();
    expect(s.match).toBeLessThanOrEqual(72);
  });
});

describe("deriveLensSummaries", () => {
  it("derives counts from the pool, not the prototype's hard-coded numbers", () => {
    const all = deriveLensSummaries(lenses, jobs).find((l) => l.id === "all")!;
    expect(all.count).toBe(13); // NOT 47
    expect(all.isNew).toBe(7); // count of isNew:true, NOT 11
  });
});

describe("sortJobs", () => {
  it("match sorts descending by match", () => {
    const sorted = sortJobs(jobs, "match");
    expect(sorted[0].match).toBeGreaterThanOrEqual(sorted[1].match);
  });
});
