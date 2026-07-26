"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Job, Candidate, JobStatus } from "@specula/shared-types";
import type { MorphRects } from "@/components/jobs/morph";
import type { Mstyle } from "@/lib/tweaks-init";
import { patchJobState, type JobStatePatch } from "@/lib/api/jobs";
import { morphScale } from "@/lib/flip";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Tag } from "@/components/atoms/tag";
import { Button } from "@/components/atoms/button";
import {
  Section,
  InsightRecord,
  SkillsSplit,
  Lifecycle,
  Feedback,
} from "@/components/jobs/drawer-sections";

export function JobDrawer({
  job,
  candidate,
  onClose,
  morphFrom = null,
  mstyle,
  onPatchState = patchJobState,
}: {
  job: Job;
  candidate: Candidate;
  onClose: () => void;
  morphFrom?: MorphRects | null;
  mstyle: Mstyle;
  onPatchState?: (id: string, patch: JobStatePatch) => void | Promise<unknown>;
}) {
  const router = useRouter();
  const reduce = usePrefersReducedMotion();
  // Optimistic local state for the posting-state controls; each edit fires a PATCH.
  const [status, setStatus] = useState<JobStatus | null>(job.status);
  const [feedback, setFeedback] = useState<"positive" | "negative" | null>(
    null,
  );
  // Fire the PATCH. On success, drop the cached RSC payload so a Back nav to /jobs shows the new
  // state (Next reuses the stale cache otherwise). On failure, revert the optimistic value so the
  // UI never claims a state that didn't persist.
  const patch = (p: JobStatePatch, revert?: () => void) => {
    const result = onPatchState(job.id, p);
    if (result instanceof Promise) {
      result.then(
        () => router.refresh(),
        () => revert?.(),
      );
    }
  };
  const handleStatus = (s: JobStatus) => {
    const prev = status;
    setStatus(s);
    patch({ status: s }, () => setStatus(prev));
  };
  const handleFeedback = (f: "positive" | "negative") => {
    const prev = feedback;
    setFeedback(f);
    patch({ feedback: f }, () => setFeedback(prev));
  };
  const handleNote = (note: string) => patch({ note });
  const panelRef = useRef<HTMLElement>(null);
  const scrimRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const meterRef = useRef<HTMLDivElement>(null);
  const closingRef = useRef(false);

  const handleClose = () => {
    if (closingRef.current) return;
    const panel = panelRef.current;
    const scrim = scrimRef.current;
    if (reduce || !panel) {
      onClose();
      return;
    }
    closingRef.current = true;
    if (scrim)
      scrim.animate([{ opacity: 1 }, { opacity: 0 }], {
        duration: 260,
        easing: "ease",
        fill: "forwards",
      });
    const a = panel.animate(
      [
        { transform: "none", opacity: 1 },
        { transform: "translateX(46px)", opacity: 0 },
      ],
      { duration: 300, easing: "cubic-bezier(.4,0,.7,1)", fill: "forwards" },
    );
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        onClose();
      }
    };
    a.onfinish = finish;
    setTimeout(finish, 360);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLayoutEffect(() => {
    const panel = panelRef.current;
    const scrim = scrimRef.current;
    if (!panel) return;
    if (scrim)
      scrim.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration: 300,
        easing: "ease",
      });
    if (reduce) return;
    if (morphFrom) {
      panel.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration: 240,
        easing: "ease",
      });
      const morph = (
        el: HTMLElement | null,
        src: DOMRect,
        srcFont: number | null,
        delay: number,
      ) => {
        if (!el) return;
        const d = el.getBoundingClientRect();
        const dx = src.left - d.left;
        const dy = src.top - d.top;
        const s = srcFont
          ? morphScale(srcFont, parseFloat(getComputedStyle(el).fontSize))
          : morphScale(src.width, d.width);
        el.animate(
          [
            {
              transform: `translate(${dx}px, ${dy}px) scale(${s})`,
              opacity: 0.55,
            },
            { transform: "none", opacity: 1 },
          ],
          {
            duration: 540,
            delay,
            easing: "cubic-bezier(.4,0,.12,1)",
            fill: "backwards",
          },
        );
      };
      morph(titleRef.current, morphFrom.title, morphFrom.titleFont, 0);
      morph(meterRef.current, morphFrom.meter, null, 40);
    } else {
      panel.animate(
        [{ transform: "translateX(100%)" }, { transform: "none" }],
        {
          duration: 440,
          easing: "cubic-bezier(.3,.9,.3,1)",
        },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div
        ref={scrimRef}
        onClick={handleClose}
        className="fixed inset-0 z-40 bg-[rgba(33,30,24,0.28)] backdrop-blur-[2px]"
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        className="fixed inset-y-0 right-0 z-[41] w-[560px] max-w-[94vw] overflow-y-auto border-l border-rule-2 bg-paper shadow-pop"
      >
        <div className="sticky top-0 z-[2] border-b border-rule bg-paper px-[28px] pt-[22px] pb-[18px]">
          <button
            onClick={handleClose}
            aria-label="Close"
            className="absolute right-[22px] top-[18px] flex h-[30px] w-[30px] items-center justify-center rounded-[7px] border border-rule-2 bg-card text-[16px] text-ink-2 hover:border-ink hover:text-ink"
          >
            ✕
          </button>
          <div className="mb-[10px] flex items-center gap-[9px] font-mono text-[11px] text-ink-2">
            <span className="flex h-[18px] w-[18px] items-center justify-center rounded-[4px] bg-panel-2 font-mono text-[8.5px] font-semibold text-ink-2">
              {job.logo}
            </span>
            {job.company}
            <span className="text-rule-2">/</span>
            {job.flag} {job.city} · {job.mode}
            {job.isNew && (
              <span className="ml-1">
                <Tag variant="new">NEW</Tag>
              </span>
            )}
          </div>
          <h2
            ref={titleRef}
            className="m-0 mr-[56px] mb-[8px] origin-top-left font-display text-[25px] font-semibold leading-[1.12] tracking-[-0.01em]"
          >
            {job.title}
          </h2>
          <div className="flex flex-wrap items-center gap-[8px] text-[13px] text-ink-2">
            <span>{job.seniority}</span>
            <span className="text-rule-2">·</span>
            <span>{job.contract}</span>
            <span className="text-rule-2">·</span>
            <span className="font-mono">posted {job.posted}</span>
          </div>
        </div>

        <div className="px-[28px] pt-[24px] pb-[60px]">
          <Section>
            <div className="mb-[16px] flex items-start gap-[22px]">
              <div ref={meterRef} className="origin-top-left">
                <MatchMeter
                  job={job}
                  mstyle={mstyle}
                  reveal={!morphFrom}
                  replay={job.id}
                />
              </div>
            </div>
            <p className="max-w-none text-[13.5px] leading-[1.5] text-ink-2">
              {job.rationale}
            </p>
            <div className="mt-[4px] flex flex-wrap items-center gap-[14px] font-mono text-[10.5px] text-ink-2">
              <OverlapBar overlap={job.overlap} />
              <span className={job.deadlineDays <= 7 ? "text-warn" : ""}>
                ↳ closes in {job.deadlineDays} days
              </span>
            </div>
          </Section>

          <Section head="summary">
            <p className="text-[14.5px] leading-[1.6] text-ink [text-wrap:pretty]">
              {job.summary}
            </p>
          </Section>

          <Section
            head="skills · required vs your profile"
            note={`${job.overlap[0]} of ${job.overlap[1]} matched`}
          >
            <SkillsSplit job={job} candidate={candidate} />
          </Section>

          <Section head="insight record" note="extracted · cached">
            <InsightRecord job={job} />
          </Section>

          <Section head="responsibilities">
            <ul className="m-0 list-disc pl-[18px] text-[13.5px] leading-[1.7] text-ink">
              {job.responsibilities.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Section>

          <Section head="application status">
            <Lifecycle
              status={status && status !== "Dismissed" ? status : null}
              note=""
              onStatus={handleStatus}
              onNote={handleNote}
            />
          </Section>

          <Section head="feedback" note="steers your recommender">
            <Feedback value={feedback} onFeedback={handleFeedback} />
          </Section>

          <div className="flex gap-[10px]">
            <Button variant="pri" className="flex-1 justify-center">
              ↗ Open posting
            </Button>
            <Button>★ Save</Button>
          </div>
        </div>
      </aside>
    </>
  );
}
