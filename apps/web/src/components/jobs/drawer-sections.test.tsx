import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import {
  InsightRecord,
  SkillsSplit,
  Lifecycle,
  Feedback,
} from "@/components/jobs/drawer-sections";
import { getJobsPool } from "@/lib/api/jobs";
import type { Candidate } from "@specula/shared-types";

afterEach(cleanup);
const base = getJobsPool()[0];

describe("drawer sections", () => {
  it("InsightRecord marks low-confidence extraction as 'surfaced, not trusted' (<75)", () => {
    render(<InsightRecord job={{ ...base, confidence: 60 }} />);
    expect(
      screen.getByText(/60% confidence — surfaced, not trusted/),
    ).toBeInTheDocument();
  });

  it("InsightRecord shows plain confidence when >= 75", () => {
    render(<InsightRecord job={{ ...base, confidence: 90 }} />);
    expect(screen.getByText("90% confidence")).toBeInTheDocument();
    expect(screen.queryByText(/surfaced, not trusted/)).toBeNull();
  });

  it("InsightRecord shows 'not stated in ad' when salary is null", () => {
    render(<InsightRecord job={{ ...base, salary: null }} />);
    expect(screen.getByText("not stated in ad")).toBeInTheDocument();
  });

  it("SkillsSplit renders have (✓) and miss (+) chips", () => {
    const cand = { skills: ["Python"] } as Candidate;
    render(
      <SkillsSplit
        job={{ ...base, stack: ["Python", "Rust"] }}
        candidate={cand}
      />,
    );
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Rust")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
    expect(screen.getByText("+")).toBeInTheDocument();
  });

  it("Lifecycle marks the current status step", () => {
    render(<Lifecycle status="Applied" note="" />);
    expect(screen.getByText("Applied")).toBeInTheDocument();
    // Saved (done, n<idx) + Applied (active, n===idx) each carry a check
    expect(screen.getAllByText("✓").length).toBe(2);
  });

  it("Feedback renders the two default (inert) controls", () => {
    render(<Feedback />);
    expect(screen.getByText("↑ Good match")).toBeInTheDocument();
    expect(screen.getByText("↓ Not for me")).toBeInTheDocument();
  });
});
