import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { OverlapBar } from "@/components/atoms/overlap-bar";

afterEach(cleanup);

describe("OverlapBar", () => {
  it("renders [m/n] req. skills", () => {
    render(<OverlapBar overlap={[8, 9]} />);
    expect(screen.getByText(/\[8\/9\] req\. skills/)).toBeInTheDocument();
  });
  it("is marked low when the ratio < 0.4", () => {
    const { container } = render(<OverlapBar overlap={[2, 8]} />);
    expect(container.querySelector('[data-low="true"]')).not.toBeNull();
  });
  it("is not low when the ratio >= 0.4", () => {
    const { container } = render(<OverlapBar overlap={[8, 9]} />);
    expect(container.querySelector('[data-low="true"]')).toBeNull();
  });
});
