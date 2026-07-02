import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { JobRow } from "@/components/jobs/job-row";
import { getJobsPool } from "@/lib/api/jobs";

afterEach(cleanup);
const pool = getJobsPool();
const base = pool[0];

describe("JobRow", () => {
  it("renders index, title, company, deadline", () => {
    render(<JobRow job={base} i={0} onOpen={() => {}} />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText(base.title)).toBeInTheDocument();
    expect(screen.getByText(base.company)).toBeInTheDocument();
    expect(
      screen.getByText(`↳ closes ${base.deadlineDays}d`),
    ).toBeInTheDocument();
  });

  it("shows the NEW tag only when isNew", () => {
    render(<JobRow job={{ ...base, isNew: true }} i={0} onOpen={() => {}} />);
    expect(screen.getByText("NEW")).toBeInTheDocument();
    cleanup();
    render(<JobRow job={{ ...base, isNew: false }} i={0} onOpen={() => {}} />);
    expect(screen.queryByText("NEW")).toBeNull();
  });

  it("shows a red-flag tag when present, and hides salary when null", () => {
    render(
      <JobRow
        job={{ ...base, redFlag: "Low required-skill overlap", salary: null }}
        i={0}
        onOpen={() => {}}
      />,
    );
    expect(
      screen.getByText(/⚑ Low required-skill overlap/),
    ).toBeInTheDocument();
    // salary hidden: no "€" and no "/yr"-style token from base.salary
    if (base.salary) expect(screen.queryByText(base.salary)).toBeNull();
  });

  it("calls onOpen with the job when clicked", () => {
    const onOpen = vi.fn();
    render(<JobRow job={base} i={2} onOpen={onOpen} />);
    fireEvent.click(screen.getByText(base.title));
    expect(onOpen).toHaveBeenCalledWith(base);
  });
});
