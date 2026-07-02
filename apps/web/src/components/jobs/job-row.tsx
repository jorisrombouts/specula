import type { Job } from "@specula/shared-types";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Tag } from "@/components/atoms/tag";

export function JobRow({
  job,
  i,
  onOpen,
}: {
  job: Job;
  i: number;
  onOpen: (job: Job) => void;
}) {
  return (
    <article
      data-fid={job.id}
      onClick={() => onOpen(job)}
      className="relative isolate grid cursor-pointer grid-cols-[30px_1fr_248px] items-start gap-[18px] border-b border-rule py-[var(--row-py)] before:absolute before:inset-y-0 before:-inset-x-[14px] before:-z-10 before:rounded-[8px] before:bg-panel before:opacity-0 before:transition-opacity hover:before:opacity-100"
    >
      <div className="pt-[4px] font-mono text-[13px] text-ink-3">
        {String(i + 1).padStart(2, "0")}
      </div>
      <div>
        <div className="flex flex-wrap items-center gap-[10px]">
          <h3 className="m-0 font-display text-[20px] font-semibold leading-[1.12] tracking-[-0.005em]">
            {job.title}
          </h3>
          {job.isNew && <Tag variant="new">NEW</Tag>}
          {job.status && job.status !== "Dismissed" && (
            <Tag variant="status">{job.status}</Tag>
          )}
        </div>
        <div className="mt-[6px] mb-[9px] flex flex-wrap items-center gap-[8px] text-[12.5px]">
          <span className="flex items-center gap-[6px] font-semibold">
            <span className="flex h-[18px] w-[18px] items-center justify-center rounded-[4px] bg-panel-2 font-mono text-[8.5px] font-semibold text-ink-2">
              {job.logo}
            </span>
            {job.company}
          </span>
          <span className="text-rule-2">/</span>
          <span className="text-ink-2">
            {job.flag} {job.city}
          </span>
          {!job.city.includes("Remote") && (
            <>
              <span className="text-rule-2">/</span>
              <span className="text-ink-2">{job.mode}</span>
            </>
          )}
          <span className="text-rule-2">/</span>
          <span className="text-ink-2">{job.seniority}</span>
          {job.salary && (
            <>
              <span className="text-rule-2">/</span>
              <span className="font-mono text-[11px] text-ink">
                {job.salary}
              </span>
            </>
          )}
        </div>
        <p className="m-0 mb-[10px] max-w-[62ch] text-[13px] leading-[1.5] text-ink-2 [text-wrap:pretty]">
          {job.rationale}
        </p>
        <div className="flex flex-wrap items-center gap-[14px] font-mono text-[10.5px] text-ink-2">
          <OverlapBar overlap={job.overlap} />
          <span className="tracking-[0.01em]">
            {job.stack.slice(0, 5).join(" · ")}
          </span>
          <span className={job.deadlineDays <= 7 ? "text-warn" : ""}>
            ↳ closes {job.deadlineDays}d
          </span>
          {job.redFlag && <Tag variant="flag">⚑ {job.redFlag}</Tag>}
          {!job.originVerified && <Tag variant="flag">⚐ origin unverified</Tag>}
        </div>
      </div>
      <MatchMeter job={job} mstyle="bars" />
    </article>
  );
}
