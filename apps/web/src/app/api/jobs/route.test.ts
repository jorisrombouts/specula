import { describe, it, expect } from "vitest";
import { GET } from "@/app/api/jobs/route";
import type { JobsResponse } from "@specula/shared-types";

async function call(url: string): Promise<JobsResponse> {
  const res = await GET(new Request(url));
  expect(res.status).toBe(200);
  return (await res.json()) as JobsResponse;
}

describe("GET /api/jobs", () => {
  it("all lens returns the full pool + derived lens summaries (not hard-coded)", async () => {
    const body = await call("http://localhost/api/jobs?lens=all&sort=match");
    expect(body.jobs).toHaveLength(13);
    const all = body.lenses.find((l) => l.id === "all")!;
    expect(all.count).toBe(13);
    expect(all.isNew).toBe(7);
    expect(body.sort).toBe("match");
  });
  it("foreign lens filters to hq!=country and re-scores loc", async () => {
    const body = await call(
      "http://localhost/api/jobs?lens=foreign&sort=match",
    );
    expect(body.jobs.map((j) => j.id).sort()).toEqual([
      "j3",
      "j4",
      "j5",
      "j7",
      "j8",
    ]);
  });
  it("sorts by match descending", async () => {
    const body = await call("http://localhost/api/jobs?lens=all&sort=match");
    expect(body.jobs[0].match).toBeGreaterThanOrEqual(body.jobs[1].match);
  });
});
