import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

afterEach(cleanup);

function mockPath(pathname: string) {
  vi.doMock("next/navigation", () => ({ usePathname: () => pathname }));
}

describe("Sidebar", () => {
  beforeEach(() => vi.resetModules());

  it("renders the brand, all six nav items, and the candidate card", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S />);
    expect(screen.getByText("Specula")).toBeInTheDocument();
    for (const label of [
      "Jobs",
      "Approval queue",
      "Companies",
      "Insights",
      "Search profiles",
      "Targeting",
    ]) {
      expect(
        screen.getByRole("link", { name: new RegExp(label, "i") }),
      ).toBeInTheDocument();
    }
    expect(
      screen.getByRole("link", { name: /candidate/i }),
    ).toBeInTheDocument();
  });

  it("marks exactly the current route active via aria-current", async () => {
    mockPath("/companies");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S />);
    const active = screen
      .getAllByRole("link")
      .filter((el) => el.getAttribute("aria-current") === "page");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAccessibleName(/companies/i);
  });

  it("fabricates no counts — renders no digit badges", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    const { container } = render(<S />);
    // No numeric count/badge text anywhere in the sidebar nav (counts are derived; none in M0a).
    expect(container.querySelector("nav")?.textContent).not.toMatch(/\d/);
  });

  it("renders the Refresh button as inert (disabled)", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S />);
    expect(screen.getByRole("button", { name: /refresh/i })).toBeDisabled();
  });
});
