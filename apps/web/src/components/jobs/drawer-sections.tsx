import { Fragment } from "react";
import type { Job, Candidate, JobStatus } from "@specula/shared-types";
import { splitSkills } from "@/components/jobs/skills";

const LIFECYCLE: JobStatus[] = ["Saved", "Applied", "Interviewing", "Offer"];

export function Section({
  head,
  note,
  children,
}: {
  head?: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-[26px]">
      {head && (
        <div className="mb-[14px] flex justify-between border-b border-rule pb-[10px] font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
          <span>{head}</span>
          {note && <span>{note}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

export function InsightRecord({ job }: { job: Job }) {
  const lowConf = job.confidence < 75;
  const rows: [string, string][] = [
    ["role family", job.title.split("—")[0].trim()],
    ["seniority", job.seniority],
    ["experience", "3–6 yrs (inferred)"],
    ["education", job.edu],
    ["work mode", job.mode],
    ["location", `${job.flag} ${job.city}`],
    ["geo", job.geo],
    ["visa", job.visa],
    ["languages", job.langs.join(", ")],
    ["salary", job.salary || "not stated in ad"],
    ["contract", job.contract],
    ["deadline", `in ${job.deadlineDays} days`],
    ["posted", job.posted],
    ["still open", job.stillOpen ? "likely open" : "likely closed"],
  ];
  return (
    <dl className="grid grid-cols-[130px_1fr] gap-x-[14px] gap-y-[7px] text-[13px]">
      {rows.map(([k, v]) => (
        <Fragment key={k}>
          <dt className="pt-px font-mono text-[11px] text-ink-2">{k}</dt>
          <dd className="m-0 text-ink">{v}</dd>
        </Fragment>
      ))}
      <dt className="pt-px font-mono text-[11px] text-ink-2">extraction</dt>
      <dd className={`m-0 ${lowConf ? "text-warn" : "text-ink"}`}>
        {job.confidence}% confidence
        {lowConf ? " — surfaced, not trusted" : ""}
      </dd>
    </dl>
  );
}

export function SkillsSplit({
  job,
  candidate,
}: {
  job: Job;
  candidate: Candidate;
}) {
  const { have, miss } = splitSkills(candidate, job.stack);
  return (
    <>
      <div className="flex flex-wrap gap-[7px]">
        {have.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-[6px] rounded-[6px] bg-accent-bg px-[10px] py-[4px] text-[12px] text-accent-ink"
          >
            <span className="font-mono text-[11px]">✓</span>
            {s}
          </span>
        ))}
        {miss.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-[6px] rounded-[6px] border border-dashed border-warn bg-warn-bg px-[10px] py-[4px] text-[12px] text-warn"
          >
            <span className="font-mono text-[11px]">+</span>
            {s}
          </span>
        ))}
      </div>
      {miss.length > 0 && (
        <p className="mt-[12px] text-[12.5px] leading-[1.5] text-ink-2">
          Gaps highlighted in amber feed your <b>skills-gap</b> view — add them
          to your profile or use them to tailor a CV bullet.
        </p>
      )}
    </>
  );
}

// M2: status steps set the lifecycle stage; the note persists on blur. Both flow up
// via onStatus/onNote → PATCH /jobs/{id}/state.
export function Lifecycle({
  status,
  note,
  onStatus,
  onNote,
}: {
  status: JobStatus | null;
  note: string;
  onStatus: (status: JobStatus) => void;
  onNote: (note: string) => void;
}) {
  const idx = status ? LIFECYCLE.indexOf(status) : -1;
  return (
    <div>
      <div className="my-[4px] flex items-center">
        {LIFECYCLE.map((s, n) => {
          const done = n < idx;
          const active = n === idx;
          return (
            <button
              key={s}
              type="button"
              aria-label={s}
              onClick={() => onStatus(s)}
              className="relative flex flex-1 cursor-pointer flex-col items-center gap-[7px] bg-transparent"
            >
              {n > 0 && (
                <span
                  className={`absolute left-[-50%] top-[9px] -z-10 h-[2px] w-full ${done ? "bg-accent" : "bg-rule"}`}
                />
              )}
              <span
                className={`z-[1] flex h-[20px] w-[20px] items-center justify-center rounded-full border-2 text-[10px] ${
                  done
                    ? "border-accent bg-accent text-white"
                    : active
                      ? "border-ink bg-ink text-white shadow-[0_0_0_4px_var(--color-panel-2)]"
                      : "border-rule-2 bg-card text-transparent"
                }`}
              >
                {n <= idx ? "✓" : ""}
              </span>
              <span
                className={`font-mono text-[9.5px] tracking-[0.02em] ${n <= idx ? "text-ink" : "text-ink-2"}`}
              >
                {s}
              </span>
            </button>
          );
        })}
      </div>
      <textarea
        className="mt-[14px] w-full resize-none rounded-[8px] border border-rule-2 bg-card px-[12px] py-[10px] font-body text-[13px] text-ink focus:border-ink focus:outline-none"
        rows={2}
        placeholder="Add a note (e.g. referred by Anna, recruiter call Tue)…"
        defaultValue={note}
        // Only persist a genuine edit — an empty/unchanged blur must not wipe a note.
        onBlur={(e) => {
          if (e.target.value !== note) onNote(e.target.value);
        }}
      />
    </div>
  );
}

// M2: like/dismiss feedback steers the recommender → PATCH /jobs/{id}/state.
export function Feedback({
  value,
  onFeedback,
}: {
  value: "positive" | "negative" | null;
  onFeedback: (feedback: "positive" | "negative") => void;
}) {
  const cls = (active: boolean) =>
    `flex flex-1 cursor-pointer items-center justify-center gap-[8px] rounded-[9px] border py-[11px] text-[13px] font-medium ${
      active
        ? "border-ink bg-panel-2 text-ink"
        : "border-rule-2 bg-card text-ink hover:border-ink"
    }`;
  return (
    <div className="flex gap-[10px]">
      <button
        type="button"
        onClick={() => onFeedback("positive")}
        className={cls(value === "positive")}
      >
        ↑ Good match
      </button>
      <button
        type="button"
        onClick={() => onFeedback("negative")}
        className={cls(value === "negative")}
      >
        ↓ Not for me
      </button>
    </div>
  );
}
