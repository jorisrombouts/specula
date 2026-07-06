import { describe, it, expect, vi } from "vitest";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getJobsPool, getJob, getJobs } = await import("@/lib/api/jobs");
const { getLenses } = await import("@/lib/api/lenses");
const { getCandidate } = await import("@/lib/api/candidate");
const { GET: jobsRoute } = await import("@/app/api/jobs/route");

describe("lib/api data-access", () => {
  it("getJobsPool returns the full 13-job pool", async () => {
    expect(await getJobsPool()).toHaveLength(13);
  });

  it("getJob returns a job by id, or null", async () => {
    expect((await getJob("j1"))?.id).toBe("j1");
    expect(await getJob("nope")).toBeNull();
  });

  it("getJobs('all','match') returns 13 jobs sorted desc by match + derived lenses", async () => {
    const res = await getJobs("all", "match");
    expect(res.jobs).toHaveLength(13);
    expect(res.sort).toBe("match");
    expect(
      res.jobs.every((j, i) => i === 0 || res.jobs[i - 1].match >= j.match),
    ).toBe(true);
    const all = res.lenses.find((l) => l.id === "all")!;
    expect(all.count).toBe(13); // DERIVED — not 47
    expect(all.isNew).toBe(7); // DERIVED — not 11
  });

  it("getJobs('foreign','match') filters + re-scores per lens", async () => {
    const res = await getJobs("foreign", "match");
    expect(res.jobs.length).toBeGreaterThan(0);
    expect(res.jobs.length).toBeLessThan(13);
  });

  it("getLenses returns 5 derived summaries", async () => {
    const ls = await getLenses();
    expect(ls).toHaveLength(5);
    expect(ls.find((l) => l.id === "all")!.count).toBe(13);
  });

  it("getCandidate returns the candidate profile", async () => {
    expect((await getCandidate()).skills.length).toBeGreaterThan(0);
  });

  it("the /api/jobs route forwards to the (BFF-fetched) JobsResponse shape", async () => {
    const res = jobsRoute(new Request("http://x/api/jobs?lens=all&sort=match"));
    const body = await (await res).json();
    expect(body.jobs).toHaveLength(13);
    expect(body.lenses.find((l: { id: string }) => l.id === "all").count).toBe(
      13,
    );
    expect(body.sort).toBe("match");
  });
});
