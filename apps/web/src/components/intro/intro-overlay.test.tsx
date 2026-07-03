import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { IntroOverlay } from "@/components/intro/intro-overlay";

afterEach(cleanup);

describe("IntroOverlay under reduced motion", () => {
  it("shows the final derived roles count immediately (13, not a stuck 0)", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: true, // prefers-reduced-motion: reduce
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    render(<IntroOverlay roles={13} isNew={7} onDone={() => {}} />);
    const stat = screen.getByText(/roles tracked/);
    expect(stat).toHaveTextContent("13");
    expect(stat).toHaveTextContent("7");
    expect(stat.textContent).not.toMatch(/\b0 roles/);
  });
});
