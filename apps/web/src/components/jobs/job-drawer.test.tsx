import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { JobDrawer } from "@/components/jobs/job-drawer";
import { getJobsPool } from "@/lib/api/jobs";
import { getCandidate } from "@/lib/api/candidate";

afterEach(cleanup);
const job = getJobsPool()[0];
const candidate = getCandidate();

describe("JobDrawer", () => {
  it("renders the title + all section heads", () => {
    render(<JobDrawer job={job} candidate={candidate} onClose={() => {}} />);
    expect(
      screen.getByRole("heading", { name: job.title }),
    ).toBeInTheDocument();
    for (const head of [
      "summary",
      "skills · required vs your profile",
      "insight record",
      "responsibilities",
      "application status",
      "feedback",
    ]) {
      expect(screen.getByText(head)).toBeInTheDocument();
    }
    expect(screen.getByText("↗ Open posting")).toBeInTheDocument();
    expect(screen.getByText("★ Save")).toBeInTheDocument();
  });

  it("closes on the ✕ button and on Escape", () => {
    const onClose = vi.fn();
    render(<JobDrawer job={job} candidate={candidate} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
