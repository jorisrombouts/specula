"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Run } from "@specula/shared-types";
import { fetchRun } from "@/lib/api/runs";

const POLL_MS = 3000;

// Triggers a long-running Run (re-score / refresh), polls it to completion, and exposes a busy
// flag, a result note (from `describe`), and a surfaced error. `onDone` fires once on a
// successful terminal run (e.g. so a page can refresh its now-updated data).
export function usePolledRun(opts: {
  trigger: () => Promise<Run>;
  describe: (run: Run) => string;
  failNote?: string;
  onDone?: (run: Run) => void;
}): {
  busy: boolean;
  note: string | null;
  error: string | null;
  start: () => void;
} {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const optsRef = useRef(opts);
  useEffect(() => {
    optsRef.current = opts;
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
      const { describe, failNote = "Action failed.", onDone } = optsRef.current;
      if (run.status === "error") {
        setError(failNote);
        return;
      }
      setNote(describe(run));
      onDone?.(run);
    },
    [stopPolling],
  );

  const start = useCallback(async () => {
    if (busy) return;
    stopPolling();
    setError(null);
    setNote(null);
    setBusy(true);

    let run: Run;
    try {
      run = await optsRef.current.trigger();
    } catch (e) {
      const fallback = optsRef.current.failNote ?? "Action failed.";
      setError(e instanceof Error ? e.message : fallback);
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

  return { busy, note, error, start };
}
