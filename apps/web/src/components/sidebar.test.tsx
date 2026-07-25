import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import type { Run } from "@specula/shared-types";

const signOut = vi.fn();
vi.mock("next-auth/react", () => ({ signOut }));

const USER = { name: "Ada Lovelace", email: "ada@example.com" };

const DONE_RUN: Run = {
  id: "r1",
  kind: "scheduled",
  status: "done",
  startedAt: "2026-07-05T08:00:00Z",
  finishedAt: "2026-07-05T08:03:00Z",
  stats: {
    found: 13,
    new: 7,
    closed: 0,
    lowConfExcluded: 1,
    errors: 0,
    scored: 0,
  },
  createdAt: "2026-07-05T08:00:00Z",
};

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
    render(<S user={USER} latestRun={null} />);
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
    render(<S user={USER} latestRun={null} />);
    const active = screen
      .getAllByRole("link")
      .filter((el) => el.getAttribute("aria-current") === "page");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAccessibleName(/companies/i);
  });

  it("fabricates no counts — renders no digit badges in the nav", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    // A finished run with a nonzero "new" count — the digit lives in the sync
    // line (outside <nav>), so the nav itself must still be digit-free.
    const { container } = render(<S user={USER} latestRun={DONE_RUN} />);
    expect(container.querySelector("nav")?.textContent ?? "").not.toMatch(/\d/);
  });

  it("renders the Refresh button enabled and triggers a POST on click", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: "r2",
        kind: "on_demand",
        status: "queued",
        startedAt: null,
        finishedAt: null,
        stats: {
          found: 0,
          new: 0,
          closed: 0,
          lowConfExcluded: 0,
          errors: 0,
          scored: 0,
        },
        createdAt: "2026-07-05T09:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<S user={USER} latestRun={DONE_RUN} />);
    const button = screen.getByRole("button", { name: /refresh now/i });
    expect(button).not.toBeDisabled();

    fireEvent.click(button);

    expect(
      await screen.findByRole("button", { name: /syncing/i }),
    ).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("renders the sync line from a provided finished run", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} latestRun={DONE_RUN} />);
    expect(screen.getByText("synced", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("falls back to 'never' / '—' when no run has ever completed", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} latestRun={null} />);
    expect(screen.getByText("never")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("reports a failed sync rather than a misleading 'synced'", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    const errorRun: Run = {
      ...DONE_RUN,
      id: "r3",
      status: "error",
      stats: {
        found: 0,
        new: 0,
        closed: 0,
        lowConfExcluded: 0,
        errors: 1,
        scored: 0,
      },
    };
    render(<S user={USER} latestRun={errorRun} />);
    expect(screen.getByText("sync failed")).toBeInTheDocument();
  });

  it("signs out on clicking Sign out", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} latestRun={null} />);
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(signOut).toHaveBeenCalledWith({ redirectTo: "/signin" });
  });
});
