"use client";

import { Button } from "@/components/atoms/button";
import { usePolledRun } from "@/lib/use-polled-run";
import { triggerRescore } from "@/lib/api/runs";

// Re-scores every existing job against the CURRENT profile (scores are otherwise frozen at the
// moment each company was approved), and reports how many were re-scored — or why it failed.
export function RescoreButton() {
  const { busy, note, error, start } = usePolledRun({
    trigger: triggerRescore,
    describe: (r) =>
      `Re-scored ${r.stats.scored} job${r.stats.scored === 1 ? "" : "s"} with your current profile.`,
    failNote: "Re-score failed.",
  });

  return (
    <div className="flex items-center gap-[12px]">
      <Button onClick={start} disabled={busy}>
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
