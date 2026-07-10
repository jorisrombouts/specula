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
  const { run, triggering, trigger } = useLatestRun(initialRun);
  // `now` is read once, at mount, via useState's lazy initializer — never
  // called inline during render, which React disallows as an impure read. A
  // pinned clock (page.clock.setFixedTime) makes this and `relative()` fully
  // deterministic for the visual suite.
  const [now] = useState(() => Date.now());
  const busy =
    triggering || run?.status === "queued" || run?.status === "running";
  const failed = !busy && run?.status === "error";

  return (
    <div className="mt-[14px] flex flex-col gap-[9px]">
      <div
        data-sync-line
        className="font-mono flex items-center gap-2 text-[11px] text-ink-2"
      >
        <span
          className={`sync-dot relative h-[7px] w-[7px] flex-shrink-0 rounded-full ${
            failed ? "bg-warn" : "bg-accent"
          }`}
        />
        {run?.finishedAt ? (
          failed ? (
            <>
              <b className="font-semibold text-ink">sync failed</b> ·{" "}
              {relative(run.finishedAt, now)}
            </>
          ) : (
            <>
              synced{" "}
              <b className="font-semibold text-ink">
                {relative(run.finishedAt, now)}
              </b>{" "}
              · <b className="font-semibold text-ink">{run.stats.new}</b> new
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
    </div>
  );
}
