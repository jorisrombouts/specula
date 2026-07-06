import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { JobDrawer } from "@/components/jobs/job-drawer";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getJobsPool } = await import("@/lib/api/jobs");
const { getCandidate } = await import("@/lib/api/candidate");

afterEach(cleanup);
const job = (await getJobsPool())[0];
const candidate = await getCandidate();

describe("JobDrawer", () => {
  it("renders the title + all section heads", () => {
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={() => {}}
        mstyle="bars"
      />,
    );
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

  it("closes (via the animation fallback) on the ✕ button", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={onClose}
        mstyle="bars"
      />,
    );
    fireEvent.click(screen.getByLabelText("Close"));
    vi.advanceTimersByTime(360); // jsdom's animate() stub never fires onfinish
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("closes (via the animation fallback) on Escape", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={onClose}
        mstyle="bars"
      />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    vi.advanceTimersByTime(360); // jsdom's animate() stub never fires onfinish
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("fires onClose only once when Escape is pressed twice within the close window", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={onClose}
        mstyle="bars"
      />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.keyDown(window, { key: "Escape" }); // second press mid-close
    vi.advanceTimersByTime(400); // past the 360ms fallback
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("reveals the MatchMeter when opened without a morph (no rects)", () => {
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={() => {}}
        mstyle="bars"
      />,
    );
    // reveal mode shows the "scoring…" label initially (MatchMeter reveal)
    expect(screen.getByText(/scoring/i)).toBeInTheDocument();
  });

  it("wires the feedback buttons to onPatchState", () => {
    const onPatchState = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={() => {}}
        mstyle="bars"
        onPatchState={onPatchState}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Good match/ }));
    expect(onPatchState).toHaveBeenCalledWith(job.id, { feedback: "positive" });
    fireEvent.click(screen.getByRole("button", { name: /Not for me/ }));
    expect(onPatchState).toHaveBeenCalledWith(job.id, { feedback: "negative" });
  });

  it("wires the lifecycle status steps to onPatchState", () => {
    const onPatchState = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={() => {}}
        mstyle="bars"
        onPatchState={onPatchState}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Applied" }));
    expect(onPatchState).toHaveBeenCalledWith(job.id, { status: "Applied" });
  });

  it("wires the note textarea to onPatchState on blur", () => {
    const onPatchState = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={() => {}}
        mstyle="bars"
        onPatchState={onPatchState}
      />,
    );
    const note = screen.getByPlaceholderText(/Add a note/);
    fireEvent.change(note, { target: { value: "recruiter call Tue" } });
    fireEvent.blur(note);
    expect(onPatchState).toHaveBeenCalledWith(job.id, {
      note: "recruiter call Tue",
    });
  });

  it("does not PATCH the note on an unchanged (empty) blur", () => {
    const onPatchState = vi.fn();
    render(
      <JobDrawer
        job={job}
        candidate={candidate}
        onClose={() => {}}
        mstyle="bars"
        onPatchState={onPatchState}
      />,
    );
    const note = screen.getByPlaceholderText(/Add a note/);
    fireEvent.blur(note); // no edit — must not wipe a persisted note
    expect(onPatchState).not.toHaveBeenCalled();
  });
});
