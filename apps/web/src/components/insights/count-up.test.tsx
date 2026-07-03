import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { CountUp } from "@/components/insights/count-up";

afterEach(cleanup);

describe("CountUp", () => {
  it("shows the final value immediately under reduced motion", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: true, // prefers-reduced-motion: reduce
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    render(<CountUp value={312} />);
    expect(screen.getByText("312")).toBeInTheDocument();
  });
});
