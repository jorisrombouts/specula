"use client";

import { useEffect, useState } from "react";
import type { Job } from "@specula/shared-types";
import { useCountUp } from "@/lib/use-count-up";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

export function matchColor(job: Job): string {
  if (job.redFlag) return "text-warn";
  if (job.match >= 85) return "text-accent";
  return "text-ink";
}

function matchColorVar(job: Job): string {
  if (job.redFlag) return "var(--color-warn)";
  if (job.match >= 85) return "var(--color-accent)";
  return "var(--color-ink)";
}

type Props = {
  job: Job;
  mstyle?: "bars" | "figure" | "ring";
  replay?: string | number;
  reveal?: boolean;
  countUp?: boolean;
};

export function MatchMeter({
  job,
  mstyle = "bars",
  replay,
  reveal = false,
  countUp = false,
}: Props) {
  const col = matchColor(job);
  const colVar = matchColorVar(job);
  const colBg = col.replace("text-", "bg-");
  const segs: [string, number][] = [
    ["ROLE", job.factors.role],
    ["SKILL", job.factors.skill],
    ["LOC", job.factors.loc],
  ];

  const [shown, setShown] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setShown(false);
    setDone(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    const t = setTimeout(() => setShown(true), reveal ? 320 : 40);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replay]);

  useEffect(() => {
    if (!shown) return;
    const t = setTimeout(() => setDone(true), reveal ? 820 : 0);
    return () => clearTimeout(t);
  }, [shown, reveal]);

  const reduce = usePrefersReducedMotion();
  const counting = countUp || reveal;
  const num = useCountUp(
    job.match,
    shown && counting && !reduce,
    reveal ? 780 : 640,
  );
  const display = counting && !reduce ? num : job.match;
  const ringDeg = (shown || reduce ? job.match : 0) * 3.6;

  // figure: 54px number, no factor bars
  if (mstyle === "figure") {
    return (
      <div className="w-[228px] shrink-0" data-style={mstyle}>
        <div className="flex items-baseline gap-[6px]">
          <span
            className={`font-mono font-semibold text-[54px] tracking-[-0.04em] leading-[0.8] ${col}`}
          >
            {display}
          </span>
          <span className="font-mono text-[12px] text-ink-3">/100</span>
        </div>
      </div>
    );
  }

  // ring: conic-gradient 74px ring + factor list
  if (mstyle === "ring") {
    return (
      <div className="w-[228px] shrink-0" data-style={mstyle}>
        <div className="flex items-center gap-[14px]">
          <div
            className="w-[74px] h-[74px] rounded-full flex items-center justify-center shrink-0"
            style={{
              background: `conic-gradient(${colVar} ${ringDeg}deg, var(--color-panel-2) 0)`,
              transition: reduce
                ? "none"
                : "background .9s cubic-bezier(.3,1,.3,1)",
            }}
          >
            <div className="w-[58px] h-[58px] rounded-full bg-card flex flex-col items-center justify-center shadow-[inset_0_0_0_1px_var(--color-rule)]">
              <span
                className={`font-mono font-semibold text-[22px] tracking-[-0.03em] ${col}`}
              >
                {display}
              </span>
              <span className="font-mono text-[7.5px] tracking-[0.12em] text-ink-2 uppercase">
                {reveal && !done ? "···" : "match"}
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-[4px]">
            {segs.map(([k, v]) => (
              <span key={k} className="font-mono text-[9px] text-ink-2">
                {k[0]}·{v}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // bars (default): meter-num 36px + /100 + label + 3 bar rows (grid 36px/1fr/24px)
  return (
    <div className="w-[228px] shrink-0" data-style={mstyle}>
      <div className="flex items-baseline gap-[6px] mb-[11px]">
        <span
          className={`font-mono font-semibold text-[36px] tracking-[-0.04em] leading-[0.8] ${col}`}
        >
          {display}
        </span>
        <span className="font-mono text-[12px] text-ink-3">/100</span>
        <span className="font-mono text-[8.5px] tracking-[0.1em] text-ink-3 ml-auto uppercase text-right leading-[1.3]">
          {reveal && !done ? (
            "scoring…"
          ) : (
            <>
              match
              <br />
              index
            </>
          )}
        </span>
      </div>
      <div className="flex flex-col gap-[6px]">
        {segs.map(([k, v]) => (
          <div
            className="grid grid-cols-[36px_1fr_24px] gap-[9px] items-center"
            key={k}
          >
            <span className="font-mono text-[8.5px] tracking-[0.05em] text-ink-2">
              {k}
            </span>
            <span className="h-[7px] bg-panel-2 rounded-[2px] overflow-hidden">
              <span
                className={`block h-full rounded-[2px] transition-[width] duration-[800ms] [transition-timing-function:cubic-bezier(0.3,1,0.3,1)] motion-reduce:transition-none ${v < 50 ? "bg-warn" : colBg}`}
                style={{ width: shown || reduce ? `${v}%` : "0%" }}
              />
            </span>
            <span className="font-mono text-[10px] text-ink-2 text-right">
              {v}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
