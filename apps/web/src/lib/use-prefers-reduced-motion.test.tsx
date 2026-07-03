import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

afterEach(cleanup);

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

describe("usePrefersReducedMotion", () => {
  it("returns false when the query does not match", () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
  });
  it("returns true when the query matches", () => {
    mockMatchMedia(true);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });
});
