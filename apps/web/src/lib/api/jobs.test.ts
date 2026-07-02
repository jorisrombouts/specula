import { describe, it, expect } from "vitest";
import { getJobsPool, getJob, getJobs } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";
import { GET as jobsRoute } from "@/app/api/jobs/route";

describe("lib/api data-access", () => {
  it("getJobsPool returns the full 13-job pool", () => {
    expect(getJobsPool()).toHaveLength(13);
  });

  it("getJob returns a job by id, or null", () => {
    expect(getJob("j1")?.id).toBe("j1");
    expect(getJob("nope")).toBeNull();
  });

  it("getJobs('all','match') returns 13 jobs sorted desc by match + derived lenses", () => {
    const res = getJobs("all", "match");
    expect(res.jobs).toHaveLength(13);
    expect(res.sort).toBe("match");
    expect(
      res.jobs.every((j, i) => i === 0 || res.jobs[i - 1].match >= j.match),
    ).toBe(true);
    const all = res.lenses.find((l) => l.id === "all")!;
    expect(all.count).toBe(13); // DERIVED — not 47
    expect(all.isNew).toBe(7); // DERIVED — not 11
  });

  it("getJobs('foreign','match') filters + re-scores per lens", () => {
    const res = getJobs("foreign", "match");
    expect(res.jobs.length).toBeGreaterThan(0);
    expect(res.jobs.length).toBeLessThan(13);
  });

  it("getLenses returns 5 derived summaries", () => {
    const ls = getLenses();
    expect(ls).toHaveLength(5);
    expect(ls.find((l) => l.id === "all")!.count).toBe(13);
  });

  it("getCandidate returns the candidate profile", () => {
    expect(getCandidate().skills.length).toBeGreaterThan(0);
  });

  it("the refactored /api/jobs route still returns the JobsResponse shape", async () => {
    const res = jobsRoute(new Request("http://x/api/jobs?lens=all&sort=match"));
    const body = await res.json();
    expect(body.jobs).toHaveLength(13);
    expect(body.lenses.find((l: { id: string }) => l.id === "all").count).toBe(
      13,
    );
    expect(body.sort).toBe("match");
  });
});
