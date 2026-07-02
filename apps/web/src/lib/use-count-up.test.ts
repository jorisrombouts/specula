import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { useCountUp } from "@/lib/use-count-up";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("useCountUp", () => {
  it("returns 0 when not running", () => {
    const { result } = renderHook(() => useCountUp(94, false, 640));
    expect(result.current).toBe(0);
  });

  it("counts up to the target and stops", () => {
    // Mock RAF to invoke the callback SYNCHRONOUSLY with an increasing timestamp
    // that jumps past the duration by the 2nd frame, so the loop terminates:
    //   frame 1 → step(700): sets start=700, progress 0;
    //   frame 2 → step(1400): progress (1400-700)/640 > 1 → sets target, no further RAF.
    let now = 0;
    vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(
      (cb: FrameRequestCallback) => {
        now += 700;
        cb(now);
        return 0;
      },
    );
    vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {});
    const { result } = renderHook(() => useCountUp(94, true, 640));
    expect(result.current).toBe(94);
  });
});
