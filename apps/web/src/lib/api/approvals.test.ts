import { describe, it, expect, vi, afterEach } from "vitest";

const { postApprovalDecision } = await import("@/lib/api/approvals");

afterEach(() => vi.restoreAllMocks());

// The component-level test (approvals-view.test.tsx) mocks postApprovalDecision out, so the
// 429 -> message parsing only runs here. Mirrors the triggerRun coverage in runs.test.ts —
// the approve path has its own rate-limit budget, so it fails this way independently.
describe("postApprovalDecision (client)", () => {
  it("POSTs the decision and resolves on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      postApprovalDecision("a1", "approve"),
    ).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/approvals/a1/decision",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ decision: "approve" }),
      }),
    );
  });

  it("surfaces a rate-limit (429) with the retry delay from the body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => ({ error: "rate_limited", retryAfterS: 30 }),
      }),
    );
    await expect(postApprovalDecision("a1", "approve")).rejects.toThrow(
      "Rate-limited — try again in 30s.",
    );
  });

  it("falls back to a generic rate-limit message when the body carries no delay", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => {
          throw new Error("not json");
        },
      }),
    );
    await expect(postApprovalDecision("a1", "approve")).rejects.toThrow(
      "Rate-limited — try again shortly.",
    );
  });

  it("surfaces a non-429 failure with the decision and its status", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(postApprovalDecision("a1", "reject")).rejects.toThrow(
      "Couldn't reject (500).",
    );
  });
});
