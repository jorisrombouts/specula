"use client";

import { useRouter } from "next/navigation";
import { usePolledRun } from "@/lib/use-polled-run";
import { triggerRefresh } from "@/lib/api/runs";
import { HeaderRefresh } from "@/components/refresh/header-refresh";

// Jobs-page refresh: re-crawls every tracked company for NEW postings, extracts + scores them,
// then refreshes the pool so they render. This is the real "tracker" refresh — unlike re-score
// (which only re-ranks the jobs you already have), it goes and fetches new jobs.
export function JobsRefreshButton() {
  const router = useRouter();
  const { busy, note, error, start } = usePolledRun({
    trigger: triggerRefresh,
    describe: (r) =>
      `Found ${r.stats.new} new job${r.stats.new === 1 ? "" : "s"}.`,
    failNote: "Refresh failed.",
    onDone: () => router.refresh(),
  });

  return (
    <HeaderRefresh
      label="Refresh jobs"
      busyLabel="Refreshing…"
      busy={busy}
      onClick={start}
      status={error ?? note}
      warn={error !== null}
    />
  );
}
