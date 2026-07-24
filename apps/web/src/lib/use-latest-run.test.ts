import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { Run } from "@specula/shared-types";

const triggerRun = vi.fn();
vi.mock("@/lib/api/runs", () => ({ triggerRun: () => triggerRun() }));

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const { useLatestRun } = await import("@/lib/use-latest-run");

const STATS = { found: 0, new: 0, closed: 0, lowConfExcluded: 0, errors: 0 };
const QUEUED: Run = {
  id: "r2",
  kind: "on_demand",
  status: "queued",
  startedAt: null,
  finishedAt: null,
  stats: STATS,
  createdAt: "2026-07-05T09:00:00Z",
};
const RUNNING: Run = { ...QUEUED, status: "running" };
const DONE: Run = {
  ...QUEUED,
  status: "done",
  startedAt: "2026-07-05T09:00:00Z",
  finishedAt: "2026-07-05T09:03:00Z",
  stats: { ...STATS, found: 5, new: 2 },
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  triggerRun.mockReset();
  refresh.mockReset();
});

describe("useLatestRun", () => {
  it("starts from the provided initial run and not triggering", () => {
    const { result } = renderHook(() => useLatestRun(null));
    expect(result.current.run).toBeNull();
    expect(result.current.triggering).toBe(false);
  });

  it("trigger() posts a run, polls until terminal, then stops and refreshes", async () => {
    vi.useFakeTimers();
    triggerRun.mockResolvedValue(QUEUED);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => RUNNING })
      .mockResolvedValueOnce({ ok: true, json: async () => DONE });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useLatestRun(null));

    await act(async () => {
      await result.current.trigger();
    });
    expect(result.current.triggering).toBe(true);
    expect(result.current.run?.status).toBe("queued");
    expect(refresh).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/runs/latest");
    expect(result.current.run?.status).toBe("running");
    expect(result.current.triggering).toBe(true);
    expect(refresh).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(result.current.run?.status).toBe("done");
    expect(result.current.triggering).toBe(false);
    expect(refresh).toHaveBeenCalledTimes(1);

    // polling has stopped — no further fetches on subsequent ticks
    const callsAfterDone = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterDone);
  });

  it("surfaces the error (and stops, without polling) when the trigger POST fails", async () => {
    triggerRun.mockRejectedValue(new Error("Rate-limited — try again in 42s."));
    const { result } = renderHook(() => useLatestRun(null));

    await act(async () => {
      await result.current.trigger();
    });

    expect(result.current.triggering).toBe(false);
    expect(result.current.run).toBeNull();
    expect(result.current.error).toBe("Rate-limited — try again in 42s.");
  });

  it("cleans up the poll interval on unmount", async () => {
    vi.useFakeTimers();
    triggerRun.mockResolvedValue(QUEUED);
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => RUNNING });
    vi.stubGlobal("fetch", fetchMock);

    const { result, unmount } = renderHook(() => useLatestRun(null));
    await act(async () => {
      await result.current.trigger();
    });
    unmount();

    const callsAtUnmount = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(12000);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAtUnmount);
  });
});
