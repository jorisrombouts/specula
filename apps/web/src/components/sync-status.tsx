"use client";

import { useState } from "react";
import type { Run } from "@specula/shared-types";
import { useLatestRun } from "@/lib/use-latest-run";

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

// Coarse, bucketed relative time (mirrors the "Nd ago" style used for posting
// dates elsewhere) so a pinned clock in the visual harness yields a stable
// string rather than drifting minute-to-minute.
function relative(finishedAt: string, now: number): string {
  const diff = Math.max(0, now - new Date(finishedAt).getTime());
  if (diff < MINUTE_MS) return "just now";
  if (diff < HOUR_MS) return `${Math.floor(diff / MINUTE_MS)}m ago`;
  if (diff < DAY_MS) return `${Math.floor(diff / HOUR_MS)}h ago`;
  return `${Math.floor(diff / DAY_MS)}d ago`;
}

// The sidebar's sync/refresh affordance: shows when the latest run finished
// (and how many new postings it found), and lets the user trigger a new one.
export function SyncStatus({ initialRun }: { initialRun: Run | null }) {
  const { run, triggering, error, trigger } = useLatestRun(initialRun);
  // `now` is read once, at mount, via useState's lazy initializer — never
  // called inline during render, which React disallows as an impure read. A
  // pinned clock (page.clock.setFixedTime) makes this and `relative()` fully
  // deterministic for the visual suite. The relative-time nodes below carry
  // suppressHydrationWarning because they are inherently client-clock-derived:
  // the server renders them against its own clock, and the client's value
  // (what the user actually sees) legitimately wins on hydration.
  const [now] = useState(() => Date.now());
  const busy =
    triggering || run?.status === "queued" || run?.status === "running";
  const failed = !busy && run?.status === "error";
  // A run can finish (`done`) yet report per-stage errors (e.g. discovery
  // queries that failed) — the API tracks the count, so surface it honestly
  // instead of showing an all-clear "synced".
  const issues = !busy && !failed ? (run?.stats.errors ?? 0) : 0;
  const warn = failed || issues > 0;

  return (
    <div className="mt-[14px] flex flex-col gap-[9px]">
      <div
        data-sync-line
        className="font-mono flex items-center gap-2 text-[11px] text-ink-2"
      >
        <span
          className={`sync-dot relative h-[7px] w-[7px] flex-shrink-0 rounded-full ${
            warn ? "bg-warn" : "bg-accent"
          }`}
        />
        {run?.finishedAt ? (
          failed ? (
            <>
              <b className="font-semibold text-ink">sync failed</b> ·{" "}
              <span suppressHydrationWarning>
                {relative(run.finishedAt, now)}
              </span>
            </>
          ) : (
            <>
              synced{" "}
              <b className="font-semibold text-ink" suppressHydrationWarning>
                {relative(run.finishedAt, now)}
              </b>{" "}
              · <b className="font-semibold text-ink">{run.stats.new}</b> new
              {issues > 0 && (
                <span className="text-warn">
                  {" "}
                  · {issues} issue{issues === 1 ? "" : "s"}
                </span>
              )}
            </>
          )
        ) : (
          <>
            synced <b className="font-semibold text-ink">never</b> ·{" "}
            <b className="font-semibold text-ink">—</b> new
          </>
        )}
      </div>
      <button
        type="button"
        disabled={busy}
        onClick={() => void trigger()}
        className="font-body mt-1 flex w-full items-center justify-center gap-[7px] rounded-[7px] bg-ink px-3 py-[9px] text-[12.5px] font-semibold text-paper disabled:opacity-60"
      >
        <span aria-hidden className={busy ? "animate-spin" : undefined}>
          ↻
        </span>{" "}
        {busy ? "Syncing…" : "Refresh now"}
      </button>
      {error ? (
        <div
          role="alert"
          className="font-mono text-[11px] leading-snug text-warn"
        >
          {error}
        </div>
      ) : null}
    </div>
  );
}
