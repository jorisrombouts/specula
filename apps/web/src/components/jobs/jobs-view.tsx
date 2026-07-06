"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type {
  Job,
  JobSort,
  JobsResponse,
  LensSummary,
  Candidate,
} from "@specula/shared-types";
import { flipDelta } from "@/lib/flip";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";
import { useTweaks } from "@/lib/tweaks";
import { LensBar } from "@/components/jobs/lens-bar";
import { JobRow } from "@/components/jobs/job-row";
import { JobDrawer } from "@/components/jobs/job-drawer";
import type { MorphRects } from "@/components/jobs/morph";

type Pos = { top: number; left: number; width: number };
type Exit = { job: Job; top: number; left: number; width: number };

export function JobsView({
  pool,
  lenses,
  candidate,
}: {
  pool: Job[];
  lenses: LensSummary[];
  candidate: Candidate;
}) {
  // The lenses come from the API default-first, so lenses[0] is the default ("All")
  // lens; its id is a real per-user UUID (not a seed sentinel).
  const defaultLensId = lenses[0]?.id ?? "";
  const [lens, setLens] = useState(defaultLensId);
  const [sort, setSort] = useState<JobSort>("match");
  const [selected, setSelected] = useState<Job | null>(null);
  const [morphFrom, setMorphFrom] = useState<MorphRects | null>(null);
  const [exiting, setExiting] = useState<Exit[]>([]);
  const reduce = usePrefersReducedMotion();
  const { tweaks } = useTweaks();
  const compact = tweaks.density === "compact";
  const cards = tweaks.layout === "cards";

  // The pool prop is the default-lens list rendered on first paint. Switching a lens (or
  // sort) re-fetches from the API, which filters + re-scores server-side per that lens —
  // the client no longer re-derives ranking (that logic was keyed to seed lens ids).
  const [list, setList] = useState<Job[]>(pool);
  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ lens, sort });
    fetch(`/api/jobs?${params}`)
      .then((r) => (r.ok ? (r.json() as Promise<JobsResponse>) : null))
      .then((data) => {
        if (!cancelled && data) setList(data.jobs);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [lens, sort]);

  const activeLens = lenses.find((l) => l.id === lens) ?? lenses[0];
  const closingSoon = list.filter(
    (j) => j.deadlineDays <= 7 && j.status !== "Applied",
  ).length;
  const newCount = pool.filter((j) => j.isNew).length;
  const sig = lens + "|" + sort;

  const openJob = (job: Job, rects: MorphRects) => {
    setSelected(job);
    setMorphFrom(rects);
  };

  const listRef = useRef<HTMLDivElement>(null);
  const flip = useRef<{
    pos: Map<string, Pos>;
    jobs: Map<string, Job>;
    init: boolean;
  }>({
    pos: new Map(),
    jobs: new Map(),
    init: false,
  });

  // FLIP: on lens/sort change, fly surviving rows old→new and fade out leavers.
  useLayoutEffect(() => {
    const cont = listRef.current;
    if (!cont) return;
    const rows = Array.from(
      cont.querySelectorAll<HTMLElement>("article[data-fid]:not([data-exit])"),
    );
    const newPos = new Map<string, Pos>();
    rows.forEach((n) =>
      newPos.set(n.dataset.fid!, {
        top: n.offsetTop,
        left: n.offsetLeft,
        width: n.offsetWidth,
      }),
    );
    const newJobs = new Map(list.map((j) => [j.id, j]));
    if (flip.current.init && !reduce) {
      rows.forEach((n) => {
        const prev = flip.current.pos.get(n.dataset.fid!);
        const next = newPos.get(n.dataset.fid!);
        if (!prev || !next) return;
        const d = flipDelta(prev, next);
        if (d) {
          n.animate(
            [
              { transform: `translate(${d.dx}px, ${d.dy}px)` },
              { transform: "none" },
            ],
            { duration: 560, easing: "cubic-bezier(.3,.9,.3,1)" },
          );
        }
      });
      const exits: Exit[] = [];
      flip.current.pos.forEach((p, id) => {
        if (!newPos.has(id)) {
          const j = flip.current.jobs.get(id);
          if (j) exits.push({ job: j, ...p });
        }
      });
      if (exits.length) {
        setExiting(exits);
        setTimeout(() => setExiting([]), 480);
      }
    }
    flip.current.pos = newPos;
    flip.current.jobs = newJobs;
    flip.current.init = true;
    // Run after the (re-fetched) list renders — the new list arriving is what drives
    // the FLIP, since lens/sort changes now resolve asynchronously via the API.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list]);

  return (
    <section
      data-screen-label="jobs"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16 motion-safe:[animation:viewIn_0.4s_cubic-bezier(0.2,0.7,0.2,1)]"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Jobs
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            One shared, deduped pool. Role &amp; skill fit are scored against
            your targeting and candidate profile; the{" "}
            <b>location factor re-scores per lens</b>, so switching a lens
            genuinely re-ranks the pool — not just filters it.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{pool.length}</b>{" "}
            in pool
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{newCount}</b> new
          </div>
        </div>
      </header>

      <LensBar lenses={lenses} active={lens} onSelect={setLens} />

      {closingSoon > 0 && (
        <div className="mt-[18px] flex items-center gap-[12px] rounded-[11px] border border-warn bg-warn-bg px-[18px] py-[13px] text-[13px] text-warn">
          ⏱{" "}
          <span>
            <b className="font-semibold">
              {closingSoon} {closingSoon === 1 ? "role" : "roles"}
            </b>{" "}
            in this lens close within 7 days — review before they disappear from
            the feed.
          </span>
        </div>
      )}

      <div className="mt-[16px] mb-[6px] flex items-center justify-between font-mono text-[11px] text-ink-2">
        <div className="flex items-center gap-[14px]">
          <span className="text-ink">{activeLens.scope}</span>
          <span>· {activeLens.modes.join(" / ")}</span>
          <span>· {activeLens.origin}</span>
          {lens !== defaultLensId && (
            <span className="text-accent-ink">
              · ◉ match re-scored for this lens
            </span>
          )}
        </div>
        <div className="flex items-center gap-[9px]">
          <span>sort</span>
          <select
            aria-label="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as JobSort)}
            className="rounded-[6px] border border-rule-2 px-[9px] py-[5px] font-mono text-[11px] text-ink"
          >
            <option value="match">match index ↓</option>
            <option value="deadline">deadline ↑</option>
            <option value="new">newest</option>
          </select>
        </div>
      </div>

      {!cards && (
        <div
          data-colhead
          className="grid grid-cols-[30px_1fr_248px] gap-[18px] border-b border-rule pt-[14px] pb-[9px] font-mono text-[9.5px] uppercase tracking-[0.08em] text-ink-3"
        >
          <span>#</span>
          <span>role / source / facts</span>
          <span>match · role / skill / loc</span>
        </div>
      )}

      <div
        ref={listRef}
        data-jlist
        data-cards={cards ? "" : undefined}
        className={
          cards ? "relative grid grid-cols-2 gap-[14px] pt-[14px]" : "relative"
        }
      >
        {list.length === 0 && (
          <div className="px-[20px] py-[80px] text-center text-ink-2">
            <div className="mb-[14px] text-[34px] opacity-40">⬚</div>
            No roles in this lens yet. Discovery runs weekly — or trigger a
            refresh.
          </div>
        )}
        {list.map((j, i) => (
          <JobRow
            key={j.id}
            job={j}
            i={i}
            onOpen={openJob}
            sig={sig}
            mstyle={tweaks.mstyle}
            compact={compact}
            card={cards}
          />
        ))}
        {exiting.map((e) => (
          <JobRow
            key={"x" + e.job.id}
            job={e.job}
            i={0}
            onOpen={openJob}
            sig={sig}
            exit
            mstyle={tweaks.mstyle}
            compact={compact}
            card={cards}
            style={{
              position: "absolute",
              top: e.top,
              left: e.left,
              width: e.width,
            }}
          />
        ))}
      </div>

      {selected && (
        <JobDrawer
          job={selected}
          candidate={candidate}
          morphFrom={morphFrom}
          mstyle={tweaks.mstyle}
          onClose={() => {
            setSelected(null);
            setMorphFrom(null);
          }}
        />
      )}
    </section>
  );
}
