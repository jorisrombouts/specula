import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
  cleanup,
} from "@testing-library/react";
import type { Run } from "@specula/shared-types";

const triggerRescore = vi.fn();
const fetchRun = vi.fn();
vi.mock("@/lib/api/runs", () => ({
  triggerRescore: () => triggerRescore(),
  fetchRun: (id: string) => fetchRun(id),
}));

const { RescoreButton } = await import("@/components/candidate/rescore-button");

const STATS = {
  found: 0,
  new: 0,
  closed: 0,
  lowConfExcluded: 0,
  errors: 0,
  scored: 0,
};
const QUEUED: Run = {
  id: "rs1",
  kind: "rescore",
  status: "queued",
  startedAt: null,
  finishedAt: null,
  stats: STATS,
  createdAt: "2026-07-25T09:00:00Z",
};
const DONE: Run = { ...QUEUED, status: "done", stats: { ...STATS, scored: 7 } };

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  triggerRescore.mockReset();
  fetchRun.mockReset();
});

describe("RescoreButton", () => {
  it("triggers a rescore, polls to done, and reports the count", async () => {
    vi.useFakeTimers();
    triggerRescore.mockResolvedValue(QUEUED);
    fetchRun.mockResolvedValue(DONE);

    render(<RescoreButton />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Re-score jobs" }));
    });
    expect(screen.getByRole("button", { name: "Re-scoring…" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(fetchRun).toHaveBeenCalledWith("rs1");
    expect(
      screen.getByText("Re-scored 7 jobs with your current profile."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Re-score jobs" })).toBeEnabled();
  });

  it("settles immediately when the run is already done (no polling needed)", async () => {
    triggerRescore.mockResolvedValue(DONE);
    render(<RescoreButton />);
    fireEvent.click(screen.getByRole("button", { name: "Re-score jobs" }));

    await waitFor(() =>
      expect(
        screen.getByText("Re-scored 7 jobs with your current profile."),
      ).toBeInTheDocument(),
    );
    expect(fetchRun).not.toHaveBeenCalled();
  });

  it("surfaces the reason when the trigger is rate-limited", async () => {
    triggerRescore.mockRejectedValue(
      new Error("Rate-limited — try again in 42s."),
    );
    render(<RescoreButton />);
    fireEvent.click(screen.getByRole("button", { name: "Re-score jobs" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Rate-limited — try again in 42s.",
      ),
    );
    expect(screen.getByRole("button", { name: "Re-score jobs" })).toBeEnabled();
  });
});
