import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import type { Run } from "@specula/shared-types";

const triggerRescore = vi.fn();
const fetchRun = vi.fn();
vi.mock("@/lib/api/runs", () => ({
  triggerRescore: () => triggerRescore(),
  fetchRun: (id: string) => fetchRun(id),
}));
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const { JobsRescoreButton } =
  await import("@/components/jobs/jobs-rescore-button");

const STATS = {
  found: 0,
  new: 0,
  closed: 0,
  lowConfExcluded: 0,
  errors: 0,
  scored: 0,
};
const DONE: Run = {
  id: "rs1",
  kind: "rescore",
  status: "done",
  startedAt: "2026-07-25T09:00:00Z",
  finishedAt: "2026-07-25T09:00:20Z",
  stats: { ...STATS, scored: 7 },
  createdAt: "2026-07-25T09:00:00Z",
};

afterEach(() => {
  cleanup();
  triggerRescore.mockReset();
  fetchRun.mockReset();
  refresh.mockReset();
});

describe("JobsRescoreButton", () => {
  it("re-scores, reports the count, and refreshes the pool", async () => {
    triggerRescore.mockResolvedValue(DONE); // already terminal → no polling
    render(<JobsRescoreButton />);

    fireEvent.click(screen.getByRole("button", { name: "Re-score jobs" }));

    await waitFor(() =>
      expect(
        screen.getByText("Re-scored 7 jobs with your current profile."),
      ).toBeInTheDocument(),
    );
    expect(refresh).toHaveBeenCalledTimes(1); // re-scored pool re-renders
  });

  it("surfaces a rate-limit as a warn alert and does not refresh", async () => {
    triggerRescore.mockRejectedValue(
      new Error("Rate-limited — try again in 42s."),
    );
    render(<JobsRescoreButton />);

    fireEvent.click(screen.getByRole("button", { name: "Re-score jobs" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Rate-limited — try again in 42s.",
      ),
    );
    expect(refresh).not.toHaveBeenCalled();
  });
});
