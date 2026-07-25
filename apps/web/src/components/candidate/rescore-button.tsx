"use client";

import { Button } from "@/components/atoms/button";
import { useRescore } from "@/lib/use-rescore";

// Re-scores every existing job against the CURRENT profile (scores are otherwise frozen at the
// moment each company was approved), and reports how many were re-scored — or why it failed.
export function RescoreButton() {
  const { busy, note, error, rescore } = useRescore();

  return (
    <div className="flex items-center gap-[12px]">
      <Button onClick={rescore} disabled={busy}>
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
