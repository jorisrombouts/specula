import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import type { DashboardSummary } from "@specula/shared-types";
import { DashboardView } from "@/components/dashboard/dashboard-view";

afterEach(cleanup);

const summary: DashboardSummary = {
  totalTokens: 1234,
  runCount: 3,
  tokensByStage: [
    { stage: "score", totalTokens: 200 },
    { stage: "extract", totalTokens: 150 },
    { stage: "embed", totalTokens: 20 },
  ],
  tokensByDay: [
    { date: "2026-07-05", totalTokens: 120, runs: 1 },
    { date: "2026-07-06", totalTokens: 250, runs: 2 },
  ],
  recentRuns: [
    {
      id: "r-2",
      kind: "on_demand",
      status: "error",
      startedAt: "2026-07-06T12:00:00Z",
      finishedAt: "2026-07-06T12:01:00Z",
      stats: {
        found: 4,
        new: 2,
        closed: 0,
        lowConfExcluded: 1,
        errors: 1,
        scored: 0,
      },
      createdAt: "2026-07-06T12:00:00Z",
      tokens: { totalTokens: 300, durationMs: 1234 },
    },
    {
      id: "r-1",
      kind: "scheduled",
      status: "done",
      startedAt: "2026-07-05T12:00:00Z",
      finishedAt: "2026-07-05T12:02:00Z",
      stats: {
        found: 13,
        new: 7,
        closed: 0,
        lowConfExcluded: 0,
        errors: 0,
        scored: 0,
      },
      createdAt: "2026-07-05T12:00:00Z",
      tokens: null,
    },
  ],
};

describe("DashboardView", () => {
  it("renders the headline total tokens and run count", () => {
    render(<DashboardView summary={summary} />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
    // Run count appears in its own tile.
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("lists each token stage", () => {
    render(<DashboardView summary={summary} />);
    for (const stage of ["score", "extract", "embed"]) {
      expect(screen.getByText(stage)).toBeInTheDocument();
    }
  });

  it("shows each recent run with its status and kind", () => {
    render(<DashboardView summary={summary} />);
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getByText("on_demand")).toBeInTheDocument();
    expect(screen.getByText("scheduled")).toBeInTheDocument();
  });

  it("renders an empty state when there is no usage or runs", () => {
    render(
      <DashboardView
        summary={{
          totalTokens: 0,
          runCount: 0,
          tokensByStage: [],
          tokensByDay: [],
          recentRuns: [],
        }}
      />,
    );
    // Both the token total and the run count tiles render "0".
    expect(screen.getAllByText("0")).toHaveLength(2);
    expect(screen.getByText(/no runs yet/i)).toBeInTheDocument();
  });
});
