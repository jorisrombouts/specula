import { describe, it, expect, vi, afterEach } from "vitest";
import { patchJobState } from "@/lib/api/jobs";

afterEach(() => vi.restoreAllMocks());

describe("patchJobState", () => {
  it("PATCHes the BFF state route and returns the reconciled patch", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "Saved", feedback: "positive" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const out = await patchJobState("j1", { status: "Saved" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/jobs/j1/state",
      expect.objectContaining({ method: "PATCH" }),
    );
    expect(out).toEqual({ status: "Saved", feedback: "positive" });
  });

  it("throws on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    );
    await expect(patchJobState("nope", { status: "Saved" })).rejects.toThrow();
  });
});
