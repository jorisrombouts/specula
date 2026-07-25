"use client";

import { useState } from "react";
import type { Run } from "@specula/shared-types";
import { useLatestRun } from "@/lib/use-latest-run";
import { relative } from "@/lib/relative-time";
import { HeaderRefresh } from "@/components/refresh/header-refresh";

// Approvals-page refresh: runs discovery (the old sidebar "Refresh now") to find new candidate
// companies — which land right here in the queue. The status line shows when discovery last ran.
export function FindCompaniesButton({
  initialRun,
}: {
  initialRun: Run | null;
}) {
  const { run, triggering, error, trigger } = useLatestRun(initialRun);
  // Read once at mount (never inline during render) so a pinned clock stays deterministic.
  const [now] = useState(() => Date.now());

  const busy =
    triggering || run?.status === "queued" || run?.status === "running";

  let status: string | null = null;
  let warn = false;
  if (error) {
    status = error;
    warn = true;
  } else if (!busy && run?.status === "error") {
    status = "Discovery failed.";
    warn = true;
  } else if (!busy && run?.finishedAt) {
    status = `checked ${relative(run.finishedAt, now)}`;
  }

  return (
    <HeaderRefresh
      label="Find new companies"
      busyLabel="Searching…"
      busy={busy}
      onClick={() => void trigger()}
      status={status}
      warn={warn}
    />
  );
}
