import { describe, it, expect } from "vitest";
import { flipDelta, morphScale } from "@/lib/flip";

describe("flip math", () => {
  it("flipDelta returns null when unmoved, delta when moved", () => {
    expect(flipDelta({ top: 10, left: 5 }, { top: 10, left: 5 })).toBeNull();
    expect(flipDelta({ top: 40, left: 5 }, { top: 10, left: 5 })).toEqual({
      dx: 0,
      dy: 30,
    });
  });
  it("morphScale is src/dest clamped to [0.3, 1.4]", () => {
    expect(morphScale(20, 25)).toBeCloseTo(0.8);
    expect(morphScale(200, 10)).toBe(1.4); // clamp high
    expect(morphScale(1, 10)).toBe(0.3); // clamp low
  });
});
