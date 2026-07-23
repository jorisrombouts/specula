import { describe, it, expect, vi } from "vitest";

// getTargeting sanitizes the lenient API read: drop out-of-ladder seniority, null preferences -> "".
vi.mock("@/lib/api/bff", () => ({
  bffFetch: async () => ({
    roleTitles: ["ML Engineer"],
    seniority: ["Senior", "Overlord"], // one valid ladder value, one out-of-ladder
    mustHaves: [],
    avoid: [],
    preferences: null, // must map to ""
  }),
}));

const { getTargeting } = await import("@/lib/api/targeting");

describe("getTargeting sanitization", () => {
  it("drops out-of-ladder seniority and maps null preferences to empty string", async () => {
    const t = await getTargeting();
    expect(t.seniority).toEqual(["Senior"]);
    expect(t.preferences).toBe("");
  });
});
