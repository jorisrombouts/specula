"use client";

import { useRouter } from "next/navigation";
import { useRescore } from "@/lib/use-rescore";
import { HeaderRefresh } from "@/components/refresh/header-refresh";

// Jobs-page refresh: re-scores every existing job against your CURRENT profile and targeting
// (scores are otherwise frozen at approval time), then refreshes the pool so the new ranking
// renders. No re-crawl — this re-ranks the jobs you have, it doesn't fetch new postings.
export function JobsRescoreButton() {
  const router = useRouter();
  const { busy, note, error, rescore } = useRescore({
    onDone: () => router.refresh(),
  });

  return (
    <HeaderRefresh
      label="Re-score jobs"
      busyLabel="Re-scoring…"
      busy={busy}
      onClick={rescore}
      status={error ?? note}
      warn={error !== null}
    />
  );
}
