import { describe, it, expect, vi } from "vitest";

// The read model is lenient (it surfaces legacy / pre-enum values instead of 500ing);
// getCandidate must sanitize those to the strict client types.
vi.mock("@/lib/api/bff", () => ({
  bffFetch: async () => ({
    headline: "Legacy",
    location: "Amsterdam, NL",
    workMode: ["Remote", "Remote, Hybrid, On-site"], // one valid, one out-of-enum
    visa: "EU visa", // legacy free-text, not a Visa option
    years: 6,
    education: [],
    languages: [],
    skills: [],
    projects: [],
    experience: [],
  }),
}));

const { getCandidate } = await import("@/lib/api/candidate");

describe("getCandidate legacy sanitization", () => {
  it("drops out-of-enum work modes and blanks an unknown visa", async () => {
    const c = await getCandidate();
    expect(c.workMode).toEqual(["Remote"]);
    expect(c.visa).toBe("");
  });
});
