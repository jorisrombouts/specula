"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Run } from "@specula/shared-types";
import { triggerRescore, fetchRun } from "@/lib/api/runs";

const POLL_MS = 3000;

// Re-scores every existing job against the CURRENT profile (scores are otherwise frozen at the
// moment each company was approved). Triggers the rescore run, polls it to completion, and
// exposes a busy flag, a result note, and a surfaced error. `onDone` fires once on a successful
// terminal run (e.g. so a page can refresh its now-re-scored data).
export function useRescore(opts?: { onDone?: (run: Run) => void }): {
  busy: boolean;
  note: string | null;
  error: string | null;
  rescore: () => void;
} {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onDoneRef = useRef(opts?.onDone);
  useEffect(() => {
    onDoneRef.current = opts?.onDone;
  });

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const settle = useCallback(
    (run: Run) => {
      stopPolling();
      setBusy(false);
      if (run.status === "error") {
        setError("Re-score failed.");
        return;
      }
      const n = run.stats.scored;
      setNote(
        `Re-scored ${n} job${n === 1 ? "" : "s"} with your current profile.`,
      );
      onDoneRef.current?.(run);
    },
    [stopPolling],
  );

  const rescore = useCallback(async () => {
    if (busy) return;
    stopPolling();
    setError(null);
    setNote(null);
    setBusy(true);

    let run: Run;
    try {
      run = await triggerRescore();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Re-score failed.");
      setBusy(false);
      return;
    }

    if (run.status === "done" || run.status === "error") {
      settle(run);
      return;
    }
    intervalRef.current = setInterval(() => {
      void (async () => {
        try {
          const latest = await fetchRun(run.id);
          if (latest.status === "done" || latest.status === "error")
            settle(latest);
        } catch {
          // transient poll failure — keep polling until the next tick
        }
      })();
    }, POLL_MS);
  }, [busy, settle, stopPolling]);

  return { busy, note, error, rescore };
}
