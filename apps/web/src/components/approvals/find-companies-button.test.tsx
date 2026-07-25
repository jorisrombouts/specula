import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import type { Run } from "@specula/shared-types";

const triggerRun = vi.fn();
vi.mock("@/lib/api/runs", () => ({ triggerRun: () => triggerRun() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const { FindCompaniesButton } =
  await import("@/components/approvals/find-companies-button");

const STATS = {
  found: 0,
  new: 0,
  closed: 0,
  lowConfExcluded: 0,
  errors: 0,
  scored: 0,
};
const FINISHED: Run = {
  id: "r1",
  kind: "on_demand",
  status: "done",
  startedAt: "2026-07-05T08:00:00Z",
  finishedAt: "2026-07-05T08:03:00Z",
  stats: { ...STATS, found: 12, new: 3 },
  createdAt: "2026-07-05T08:00:00Z",
};

afterEach(() => {
  cleanup();
  triggerRun.mockReset();
});

describe("FindCompaniesButton", () => {
  it("shows a 'checked …' status from the last discovery run", () => {
    render(<FindCompaniesButton initialRun={FINISHED} />);
    expect(screen.getByText(/^checked /)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Find new companies" }),
    ).toBeEnabled();
  });

  it("triggers discovery and enters the searching state", async () => {
    triggerRun.mockResolvedValue({ ...FINISHED, status: "queued" });
    render(<FindCompaniesButton initialRun={null} />);

    fireEvent.click(screen.getByRole("button", { name: "Find new companies" }));

    expect(
      await screen.findByRole("button", { name: "Searching…" }),
    ).toBeDisabled();
    await waitFor(() => expect(triggerRun).toHaveBeenCalledTimes(1));
  });

  it("surfaces a rate-limit as a warn alert", async () => {
    triggerRun.mockRejectedValue(new Error("Rate-limited — try again in 42s."));
    render(<FindCompaniesButton initialRun={null} />);

    fireEvent.click(screen.getByRole("button", { name: "Find new companies" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Rate-limited — try again in 42s.",
      ),
    );
  });
});
