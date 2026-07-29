import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import type { Job } from "@specula/shared-types";
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

  // "Refresh jobs" completes -> JobsRefreshButton calls router.refresh() -> the server
  // component re-renders and hands down a NEW pool prop. These two cover what the client
  // does with that, and what it does when the re-fetch fails.
  describe("when a refreshed pool prop arrives", () => {
    afterEach(() => vi.unstubAllGlobals());

    const brandNew = {
      ...props.pool[0],
      id: "job-new-1",
      title: "Brand New Role",
    };

    // TweaksProvider also hits fetch (/api/tweaks), so the stub dispatches on URL rather
    // than call order — otherwise a queued jobs response gets handed to the wrong caller.
    // Returns the array of /api/jobs URLs actually requested.
    type JobsReply = { jobs: Job[] } | "reject";
    function stubFetch(replies: JobsReply[]): string[] {
      const jobsCalls: string[] = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string) => {
          if (!url.startsWith("/api/jobs")) {
            return { ok: true, json: async () => ({}) };
          }
          const reply = replies[Math.min(jobsCalls.length, replies.length - 1)];
          jobsCalls.push(url);
          if (reply === "reject") throw new Error("network down");
          return { ok: true, json: async () => reply };
        }),
      );
      return jobsCalls;
    }

    it("re-fetches for the active lens and renders the new jobs", async () => {
      // Mount gets the original pool; the pool change must drive a SECOND jobs fetch.
      // Without it the new job never reaches the list.
      const jobsCalls = stubFetch([
        { jobs: props.pool },
        { jobs: [brandNew, ...props.pool] },
      ]);

      const { rerender } = render(
        <TweaksProvider>
          <JobsView {...props} />
        </TweaksProvider>,
      );
      await act(async () => {});
      expect(jobsCalls).toHaveLength(1);
      expect(screen.queryByText("Brand New Role")).toBeNull();

      rerender(
        <TweaksProvider>
          <JobsView {...props} pool={[brandNew, ...props.pool]} />
        </TweaksProvider>,
      );
      await act(async () => {});

      expect(jobsCalls).toHaveLength(2);
      expect(screen.getByText("Brand New Role")).toBeInTheDocument();
    });

    it("surfaces a failed lens fetch instead of silently showing the previous lens", async () => {
      stubFetch([{ jobs: props.pool }, "reject"]);

      render(
        <TweaksProvider>
          <JobsView {...props} />
        </TweaksProvider>,
      );
      await act(async () => {});

      // Switching lens triggers the second (failing) fetch. The rows on screen still
      // belong to the previous lens, so the UI must say so rather than mislabel them.
      fireEvent.click(screen.getByRole("button", { name: /Remote · EU/ }));
      await act(async () => {});

      expect(screen.getByRole("status")).toHaveTextContent(/couldn't load/i);
    });
  });
});
