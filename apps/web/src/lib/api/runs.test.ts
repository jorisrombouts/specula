import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getLatestRun, getRun, triggerRun } = await import("@/lib/api/runs");
const { GET: latestRoute } = await import("@/app/api/runs/latest/route");
const { POST: runsRoute } = await import("@/app/api/runs/route");
const { runApiFixture } = await import("@/lib/api/test-fixtures");

afterEach(() => vi.restoreAllMocks());

describe("lib/api/runs data-access", () => {
  it("getLatestRun returns the demo user's latest (seeded, finished) run", async () => {
    const run = await getLatestRun();
    expect(run?.id).toBe(runApiFixture.id);
    expect(run?.status).toBe("done");
    expect(run?.stats.new).toBe(7);
  });

  it("getRun returns a run by id", async () => {
    const run = await getRun(runApiFixture.id);
    expect(run.id).toBe(runApiFixture.id);
  });

  it("the /api/runs/latest route forwards the same shape (server + client polling both hit this)", async () => {
    const body = await (await latestRoute()).json();
    expect(body.id).toBe(runApiFixture.id);
  });

  it("the /api/runs route POSTs to FastAPI and returns 201 with a freshly queued run", async () => {
    const res = await runsRoute();
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.status).toBe("queued");
    expect(body.finishedAt).toBeNull();
  });
});

describe("triggerRun (client)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("POSTs /api/runs and returns the created run", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ ...runApiFixture, status: "queued" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const run = await triggerRun();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs",
      expect.objectContaining({ method: "POST" }),
    );
    expect(run.status).toBe("queued");
  });

  it("throws on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(triggerRun()).rejects.toThrow();
  });
});
