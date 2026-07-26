import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import type { Run } from "@specula/shared-types";

const triggerRefresh = vi.fn();
const fetchRun = vi.fn();
vi.mock("@/lib/api/runs", () => ({
  triggerRefresh: () => triggerRefresh(),
  fetchRun: (id: string) => fetchRun(id),
}));
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const { JobsRefreshButton } =
  await import("@/components/jobs/jobs-refresh-button");

const STATS = {
  found: 0,
  new: 0,
  closed: 0,
  lowConfExcluded: 0,
  errors: 0,
  scored: 0,
};
const DONE: Run = {
  id: "rf1",
  kind: "refresh",
  status: "done",
  startedAt: "2026-07-26T09:00:00Z",
  finishedAt: "2026-07-26T09:01:00Z",
  stats: { ...STATS, new: 3 },
  createdAt: "2026-07-26T09:00:00Z",
};

afterEach(() => {
  cleanup();
  triggerRefresh.mockReset();
  fetchRun.mockReset();
  refresh.mockReset();
});

describe("JobsRefreshButton", () => {
  it("re-crawls, reports new jobs found, and refreshes the pool", async () => {
    triggerRefresh.mockResolvedValue(DONE); // already terminal → no polling
    render(<JobsRefreshButton />);

    fireEvent.click(screen.getByRole("button", { name: "Refresh jobs" }));

    await waitFor(() =>
      expect(screen.getByText("Found 3 new jobs.")).toBeInTheDocument(),
    );
    expect(refresh).toHaveBeenCalledTimes(1); // new/re-scored pool re-renders
  });

  it("surfaces a rate-limit as a warn alert and does not refresh", async () => {
    triggerRefresh.mockRejectedValue(
      new Error("Rate-limited — try again in 42s."),
    );
    render(<JobsRefreshButton />);

    fireEvent.click(screen.getByRole("button", { name: "Refresh jobs" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Rate-limited — try again in 42s.",
      ),
    );
    expect(refresh).not.toHaveBeenCalled();
  });
});
