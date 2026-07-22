import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import type { DashboardSummary } from "@specula/shared-types";
import { DashboardView } from "@/components/dashboard/dashboard-view";

afterEach(cleanup);

const summary: DashboardSummary = {
  totalCostUsd: 0.37,
  runCount: 3,
  costByStage: [
    { stage: "score", costUsd: 0.2 },
    { stage: "extract", costUsd: 0.15 },
    { stage: "embed", costUsd: 0.02 },
  ],
  costByDay: [
    { date: "2026-07-05", costUsd: 0.12, runs: 1 },
    { date: "2026-07-06", costUsd: 0.25, runs: 2 },
  ],
  recentRuns: [
    {
      id: "r-2",
      kind: "on_demand",
      status: "error",
      startedAt: "2026-07-06T12:00:00Z",
      finishedAt: "2026-07-06T12:01:00Z",
      stats: { found: 4, new: 2, closed: 0, lowConfExcluded: 1, errors: 1 },
      createdAt: "2026-07-06T12:00:00Z",
      cost: { costUsd: 0.3, durationMs: 1234 },
    },
    {
      id: "r-1",
      kind: "scheduled",
      status: "done",
      startedAt: "2026-07-05T12:00:00Z",
      finishedAt: "2026-07-05T12:02:00Z",
      stats: { found: 13, new: 7, closed: 0, lowConfExcluded: 0, errors: 0 },
      createdAt: "2026-07-05T12:00:00Z",
      cost: null,
    },
  ],
};

describe("DashboardView", () => {
  it("renders the headline total spend and run count", () => {
    render(<DashboardView summary={summary} />);
    expect(screen.getByText("$0.37")).toBeInTheDocument();
    // Run count appears in its own tile.
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("lists each spend stage", () => {
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

  it("renders an empty state when there is no spend or runs", () => {
    render(
      <DashboardView
        summary={{
          totalCostUsd: 0,
          runCount: 0,
          costByStage: [],
          costByDay: [],
          recentRuns: [],
        }}
      />,
    );
    expect(screen.getByText("$0.00")).toBeInTheDocument();
    expect(screen.getByText(/no runs yet/i)).toBeInTheDocument();
  });
});
