"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Run } from "@specula/shared-types";
import { Button } from "@/components/atoms/button";
import { triggerRescore, fetchRun } from "@/lib/api/runs";

const POLL_MS = 3000;

// Re-scores every existing job against the CURRENT profile (scores are otherwise frozen at the
// moment each company was approved). Triggers the rescore run, then polls it to completion and
// reports how many jobs were re-scored — or why it failed (e.g. a rate-limit).
export function RescoreButton() {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
      } else {
        const n = run.stats.scored;
        setNote(
          `Re-scored ${n} job${n === 1 ? "" : "s"} with your current profile.`,
        );
      }
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

  return (
    <div className="flex items-center gap-[12px]">
      <Button onClick={() => void rescore()} disabled={busy}>
        {busy ? "Re-scoring…" : "Re-score jobs"}
      </Button>
      {note ? <span className="text-[12.5px] text-ink-2">{note}</span> : null}
      {error ? (
        <span role="alert" className="font-mono text-[11.5px] text-warn">
          {error}
        </span>
      ) : null}
    </div>
  );
}
