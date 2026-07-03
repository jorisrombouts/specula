"use client";

import { useState } from "react";
import type {
  Job,
  JobSort,
  LensSummary,
  Candidate,
} from "@specula/shared-types";
import { scoredList } from "@/lib/jobs-scoring";
import { LensBar } from "@/components/jobs/lens-bar";
import { JobRow } from "@/components/jobs/job-row";
import { JobDrawer } from "@/components/jobs/job-drawer";

export function JobsView({
  pool,
  lenses,
  candidate,
}: {
  pool: Job[];
  lenses: LensSummary[];
  candidate: Candidate;
}) {
  const [lens, setLens] = useState("all");
  const [sort, setSort] = useState<JobSort>("match");
  const [selected, setSelected] = useState<Job | null>(null);

  const list = scoredList(pool, lens, sort);
  const activeLens = lenses.find((l) => l.id === lens) ?? lenses[0];
  const closingSoon = list.filter(
    (j) => j.deadlineDays <= 7 && j.status !== "Applied",
  ).length;
  const newCount = pool.filter((j) => j.isNew).length;

  return (
    <section
      data-screen-label="jobs"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
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
          {lens !== "all" && (
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

      <div className="grid grid-cols-[30px_1fr_248px] gap-[18px] border-b border-rule pt-[14px] pb-[9px] font-mono text-[9.5px] uppercase tracking-[0.08em] text-ink-3">
        <span>#</span>
        <span>role / source / facts</span>
        <span>match · role / skill / loc</span>
      </div>

      <div className="relative">
        {list.length === 0 && (
          <div className="px-[20px] py-[80px] text-center text-ink-2">
            <div className="mb-[14px] text-[34px] opacity-40">⬚</div>
            No roles in this lens yet. Discovery runs weekly — or trigger a
            refresh.
          </div>
        )}
        {list.map((j, i) => (
          <JobRow key={j.id} job={j} i={i} onOpen={setSelected} />
        ))}
      </div>

      {selected && (
        <JobDrawer
          job={selected}
          candidate={candidate}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
