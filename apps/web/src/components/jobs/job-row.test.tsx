import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { JobRow } from "@/components/jobs/job-row";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getJobsPool } = await import("@/lib/api/jobs");

afterEach(cleanup);
const pool = await getJobsPool();
const base = pool[0];

describe("JobRow", () => {
  it("renders index, title, company, deadline", () => {
    render(
      <JobRow
        job={base}
        i={0}
        onOpen={() => {}}
        sig="all|match"
        mstyle="bars"
      />,
    );
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText(base.title)).toBeInTheDocument();
    expect(screen.getByText(base.company)).toBeInTheDocument();
    expect(
      screen.getByText(`↳ closes ${base.deadlineDays}d`),
    ).toBeInTheDocument();
  });

  it("shows the NEW tag only when isNew", () => {
    render(
      <JobRow
        job={{ ...base, isNew: true }}
        i={0}
        onOpen={() => {}}
        sig="all|match"
        mstyle="bars"
      />,
    );
    expect(screen.getByText("NEW")).toBeInTheDocument();
    cleanup();
    render(
      <JobRow
        job={{ ...base, isNew: false }}
        i={0}
        onOpen={() => {}}
        sig="all|match"
        mstyle="bars"
      />,
    );
    expect(screen.queryByText("NEW")).toBeNull();
  });

  it("shows a red-flag tag when present, and hides salary when null", () => {
    render(
      <JobRow
        job={{ ...base, redFlag: "Low required-skill overlap", salary: null }}
        i={0}
        onOpen={() => {}}
        sig="all|match"
        mstyle="bars"
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
    render(
      <JobRow job={base} i={2} onOpen={onOpen} sig="all|match" mstyle="bars" />,
    );
    fireEvent.click(screen.getByText(base.title));
    expect(onOpen).toHaveBeenCalledWith(
      base,
      expect.objectContaining({ title: expect.anything() }),
    );
  });

  it("renders an exit row (non-interactive, positioned) without crashing", () => {
    const onOpen = vi.fn();
    const { container } = render(
      <JobRow
        job={base}
        i={0}
        onOpen={onOpen}
        sig="all|match"
        mstyle="bars"
        exit
        style={{ top: 5 }}
      />,
    );
    const article = container.querySelector("article[data-fid]")!;
    expect(article.getAttribute("data-exit")).toBe("");
    // exit rows don't open the drawer
    fireEvent.click(article);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("an exit row in card mode keeps the card layout (not the 3-col row grid)", () => {
    const { container } = render(
      <JobRow
        job={base}
        i={0}
        onOpen={() => {}}
        sig="all|match"
        mstyle="bars"
        card
        exit
        style={{ top: 5 }}
      />,
    );
    const article = container.querySelector("article[data-fid]")!;
    // card layout = flex flex-col + rounded card; NOT the row 3-col grid template
    expect(article.className).toContain("flex-col");
    expect(article.className).toContain("rounded-[14px]");
    expect(article.className).not.toContain("grid-cols-[30px_1fr_248px]");
    // still an exit row (fades out, non-interactive)
    expect(article.getAttribute("data-exit")).toBe("");
    expect(article.className).toContain("rowExit");
  });
});
