import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
  act,
} from "@testing-library/react";
import { JobsView } from "@/components/jobs/jobs-view";
import { getJobsPool } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";

afterEach(cleanup);
const props = {
  pool: getJobsPool(),
  lenses: getLenses(),
  candidate: getCandidate(),
};

describe("JobsView", () => {
  it("renders DERIVED header counts (13 in pool · 7 new)", () => {
    // <header> nested in <section> is NOT a `banner` landmark — query the
    // element directly. The header prose contains no digits, so the only
    // "13"/"7" come from the derived pool/new counts.
    const { container } = render(<JobsView {...props} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("13");
    expect(header).toHaveTextContent("in pool");
    expect(header).toHaveTextContent("7");
    expect(header).toHaveTextContent("new");
  });

  it("renders all 13 rows in the default (all) lens", () => {
    const { container } = render(<JobsView {...props} />);
    expect(container.querySelectorAll("article[data-fid]")).toHaveLength(13);
  });

  it("shows the deadline banner (some role closes within 7 days)", () => {
    render(<JobsView {...props} />);
    expect(screen.getByText(/close within 7 days/)).toBeInTheDocument();
  });

  it("switching to a non-all lens shows the re-scored toolbar note", () => {
    render(<JobsView {...props} />);
    expect(screen.queryByText(/match re-scored for this lens/)).toBeNull();
    // "Remote" also appears in job-mode spans + the toolbar, so scope to the
    // lens buttons (the only <button>s until the drawer opens).
    const remoteBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("Remote"))!;
    fireEvent.click(remoteBtn);
    expect(
      screen.getByText(/match re-scored for this lens/),
    ).toBeInTheDocument();
  });

  it("opens the drawer for a clicked row and closes it on Escape", () => {
    vi.useFakeTimers();
    render(<JobsView {...props} />);
    const firstRow = document.querySelector("article[data-fid]") as HTMLElement;
    const title = within(firstRow).getByRole("heading").textContent!;
    fireEvent.click(firstRow);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: title, level: 2 }),
    ).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    act(() => {
      vi.advanceTimersByTime(360); // jsdom's animate() stub never fires onfinish
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    vi.useRealTimers();
  });
});
