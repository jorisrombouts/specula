import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
  act,
} from "@testing-library/react";
import { JobsView } from "@/components/jobs/jobs-view";
import { TweaksProvider } from "@/lib/tweaks";
import { STORAGE_KEY } from "@/lib/tweaks-init";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const { getJobsPool } = await import("@/lib/api/jobs");
const { getLenses } = await import("@/lib/api/lenses");
const { getCandidate } = await import("@/lib/api/candidate");

afterEach(cleanup);
beforeEach(() => localStorage.clear());
const props = {
  pool: await getJobsPool(),
  lenses: await getLenses(),
  candidate: await getCandidate(),
};

function renderView(tweaks?: Record<string, unknown>) {
  if (tweaks) localStorage.setItem(STORAGE_KEY, JSON.stringify(tweaks));
  return render(
    <TweaksProvider>
      <JobsView {...props} />
    </TweaksProvider>,
  );
}

describe("JobsView", () => {
  it("renders DERIVED header counts (13 in pool · 7 new)", () => {
    // <header> nested in <section> is NOT a `banner` landmark — query the
    // element directly. The header prose contains no digits, so the only
    // "13"/"7" come from the derived pool/new counts.
    const { container } = renderView();
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("13");
    expect(header).toHaveTextContent("in pool");
    expect(header).toHaveTextContent("7");
    expect(header).toHaveTextContent("new");
  });

  it("renders all 13 rows in the default (all) lens", () => {
    const { container } = renderView();
    expect(container.querySelectorAll("article[data-fid]")).toHaveLength(13);
  });

  it("shows the deadline banner (some role closes within 7 days)", () => {
    renderView();
    expect(screen.getByText(/close within 7 days/)).toBeInTheDocument();
  });

  it("switching to a non-all lens shows the re-scored toolbar note", () => {
    renderView();
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
    renderView();
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

  it("passes the mstyle tweak to the row meters (figure style)", () => {
    const { container } = renderView({ mstyle: "figure" });
    // figure style renders the 54px number with data-style="figure"
    expect(container.querySelector('[data-style="figure"]')).not.toBeNull();
  });

  it("hides the row rationale under compact density", async () => {
    const { container } = renderView({ density: "compact" });
    // rationale paragraph carries data-jrat; hidden when compact
    await Promise.resolve();
    expect(container.querySelector("[data-jrat]")).toBeNull();
  });

  it("renders the Jobs list as a 2-col card grid under layout=cards (no colhead)", () => {
    const { container } = renderView({ layout: "cards" });
    // the list container becomes a grid; the column header is hidden
    expect(container.querySelector("[data-jlist][data-cards]")).not.toBeNull();
    expect(container.querySelector("[data-colhead]")).toBeNull();
    // rows carry the card marker
    expect(
      container.querySelector("article[data-fid][data-card]"),
    ).not.toBeNull();
  });
});
