import type { Job } from "@specula/shared-types";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Tag } from "@/components/atoms/tag";

export function JobRow({
  job,
  i,
  onOpen,
  sig,
  exit = false,
  style,
}: {
  job: Job;
  i: number;
  onOpen: (job: Job) => void;
  sig: string;
  exit?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <article
      data-fid={job.id}
      data-exit={exit ? "" : undefined}
      onClick={() => !exit && onOpen(job)}
      style={exit ? style : { animationDelay: `${i * 45}ms` }}
      className={
        "relative isolate grid grid-cols-[30px_1fr_248px] items-start gap-[18px] border-b border-rule py-[var(--row-py)] " +
        (exit
          ? "pointer-events-none z-0 [animation:rowExit_0.46s_cubic-bezier(0.4,0,0.6,1)_forwards]"
          : "cursor-pointer opacity-0 motion-safe:[animation:rowIn_0.5s_cubic-bezier(0.2,0.7,0.2,1)_forwards] motion-reduce:opacity-100 before:absolute before:inset-y-0 before:-inset-x-[14px] before:-z-10 before:rounded-[8px] before:bg-panel before:opacity-0 before:transition-opacity hover:before:opacity-100")
      }
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
      <MatchMeter job={job} mstyle="bars" replay={sig} countUp={!exit} />
    </article>
  );
}
