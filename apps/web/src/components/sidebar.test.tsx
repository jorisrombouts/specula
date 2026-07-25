import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

const signOut = vi.fn();
vi.mock("next-auth/react", () => ({ signOut }));

const USER = { name: "Ada Lovelace", email: "ada@example.com" };

afterEach(() => {
  cleanup();
  signOut.mockClear();
  vi.unstubAllGlobals();
});

function mockPath(pathname: string) {
  vi.doMock("next/navigation", () => ({
    usePathname: () => pathname,
    useRouter: () => ({ refresh: vi.fn() }),
  }));
}

describe("Sidebar", () => {
  beforeEach(() => vi.resetModules());

  it("renders the brand, all six nav items, and the signed-in identity", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
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
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
  });

  it("marks exactly the current route active via aria-current", async () => {
    mockPath("/companies");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    const active = screen
      .getAllByRole("link")
      .filter((el) => el.getAttribute("aria-current") === "page");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAccessibleName(/companies/i);
  });

  it("fabricates no counts — renders no digit badges in the nav", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    const { container } = render(<S user={USER} />);
    expect(container.querySelector("nav")?.textContent ?? "").not.toMatch(/\d/);
  });

  it("no longer renders a refresh control (moved to the Jobs & Companies pages)", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    expect(screen.queryByRole("button", { name: /refresh/i })).toBeNull();
    expect(screen.queryByText(/synced/i)).toBeNull();
  });

  it("signs out on clicking Sign out", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(signOut).toHaveBeenCalledWith({ redirectTo: "/signin" });
  });
});
