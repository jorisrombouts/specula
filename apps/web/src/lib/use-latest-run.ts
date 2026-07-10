"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Run } from "@specula/shared-types";
import { triggerRun as postRun } from "@/lib/api/runs";

const POLL_MS = 3000;

// Drives the sidebar's "Refresh now" affordance: triggers a run, optimistically
// shows it as queued, then polls the BFF's /runs/latest every ~3s while the run
// is in flight, stopping (and refreshing server components) once it reaches a
// terminal status.
export function useLatestRun(initialRun: Run | null): {
  run: Run | null;
  triggering: boolean;
  trigger: () => Promise<void>;
} {
  const [run, setRun] = useState<Run | null>(initialRun);
  const [triggering, setTriggering] = useState(false);
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Clean up a still-running poll on unmount.
  useEffect(() => stopPolling, [stopPolling]);

  const trigger = useCallback(async () => {
    if (triggering) return;
    stopPolling();
    setTriggering(true);
    try {
      setRun(await postRun());
    } catch {
      setTriggering(false);
      return;
    }

    intervalRef.current = setInterval(() => {
      void (async () => {
        try {
          const res = await fetch("/api/runs/latest");
          if (!res.ok) return;
          const latest = (await res.json()) as Run | null;
          if (!latest) return;
          setRun(latest);
          if (latest.status === "done" || latest.status === "error") {
            stopPolling();
            setTriggering(false);
            router.refresh();
          }
        } catch {
          // transient poll failure — keep polling until the next tick
        }
      })();
    }, POLL_MS);
  }, [router, stopPolling, triggering]);

  return { run, triggering, trigger };
}
