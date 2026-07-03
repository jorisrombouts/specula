import type { Insights } from "@specula/shared-types";
import { Tag } from "@/components/atoms/tag";
import { CountUp } from "@/components/insights/count-up";
import { DemandTrend } from "@/components/insights/demand-trend";

function Panel({
  title,
  sub,
  children,
}: {
  title: string;
  sub: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[14px] border border-rule bg-card p-[20px_22px] shadow-card">
      <div className="mb-[18px] flex items-baseline justify-between">
        <span className="font-display text-[17px] font-semibold">{title}</span>
        <span className="font-mono text-[10.5px] text-ink-2">{sub}</span>
      </div>
      {children}
    </div>
  );
}

export function InsightsView({ insights: ins }: { insights: Insights }) {
  const seniorMax = Math.max(...ins.seniorityMix.map((s) => s.v));
  return (
    <section
      data-screen-label="insights"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Insights
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Personal market intelligence — aggregates over every structured
            posting you&apos;ve collected. Most trackers can&apos;t show this
            because they never parse the ads. Low-confidence extractions are
            excluded.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <select
            defaultValue="8w"
            aria-label="period"
            className="rounded-[6px] border border-rule-2 bg-card px-[9px] py-[5px] font-mono text-[12px] text-ink"
          >
            <option value="4w">Last 4 weeks</option>
            <option value="8w">Last 8 weeks</option>
            <option value="q">This quarter</option>
          </select>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">
              <CountUp value={ins.totalAnalysed} />
            </b>{" "}
            analysed
          </div>
        </div>
      </header>

      <p className="mt-[16px] text-[12.5px] leading-[1.5] text-ink-2">
        ⚐ {ins.lowConfExcluded} low-confidence extractions excluded from every
        aggregate below. Treat trends as directional.
      </p>

      <div className="mt-[22px] grid grid-cols-2 gap-[18px]">
        <Panel title="Skill demand" sub="% of postings · Δ vs 8w ago">
          <div className="flex flex-col gap-[13px]">
            {ins.skillDemand.map((s) => (
              <div
                key={s.skill}
                className="grid grid-cols-[120px_1fr_64px] items-center gap-[12px]"
              >
                <span className="text-[12.5px] font-medium">
                  {s.skill}
                  {s.gap && (
                    <span className="ml-[6px] text-[9px]">
                      <Tag variant="flag">gap</Tag>
                    </span>
                  )}
                </span>
                <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
                  <span
                    className={`block h-full origin-left rounded-[3px] motion-safe:[animation:barGrow_0.9s_cubic-bezier(0.3,1,0.3,1)] ${s.up ? "bg-accent" : "bg-ink"}`}
                    style={{ width: `${s.pct}%` }}
                  />
                </span>
                <span
                  className={`text-right font-mono text-[11px] ${s.delta >= 0 ? "text-accent" : "text-warn"}`}
                >
                  {s.delta >= 0 ? "▲" : "▼"} {Math.abs(s.delta)}%
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Demand drift" sub="stacked, weekly">
          <DemandTrend trend={ins.trend} />
        </Panel>

        <Panel title="Seniority mix" sub="% of pool">
          <div className="flex flex-col gap-[13px]">
            {ins.seniorityMix.map((s) => (
              <div
                key={s.k}
                className="grid grid-cols-[120px_1fr_64px] items-center gap-[12px]"
              >
                <span className="text-[12.5px] font-medium">{s.k}</span>
                <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
                  <span
                    className="block h-full origin-left rounded-[3px] motion-safe:[animation:barGrow_0.9s_cubic-bezier(0.3,1,0.3,1)]"
                    style={{
                      width: `${(s.v / seniorMax) * 100}%`,
                      background:
                        s.k === "Senior" ? "var(--accent)" : "var(--ink)",
                    }}
                  />
                </span>
                <span className="text-right font-mono text-[11px] text-ink-2">
                  {s.v}%
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Work-mode mix" sub="& its drift">
          <div className="mb-[14px] flex h-[38px] overflow-hidden rounded-[9px]">
            {ins.modeMix.map((m) => (
              <div
                key={m.k}
                className="flex items-center justify-center font-mono text-[11px] font-semibold text-white"
                style={{ flex: m.v, background: m.color }}
              >
                {m.v}%
              </div>
            ))}
          </div>
          <div className="flex gap-[16px] font-mono text-[10.5px] text-ink-2">
            {ins.modeMix.map((m) => (
              <span key={m.k} className="flex items-center gap-[6px]">
                <i
                  className="h-[9px] w-[9px] rounded-[2px]"
                  style={{ background: m.color }}
                />
                {m.k}
              </span>
            ))}
          </div>
          <p className="mt-[14px] text-[12.5px] leading-[1.5] text-ink-2">
            Remote share is up <b className="text-accent-ink">+5pts</b> over 8
            weeks — good news for your remote-EU lens.
          </p>
        </Panel>

        <Panel title="Salary distribution" sub="where listed · informational">
          <div className="flex flex-col gap-[11px]">
            {ins.salary.map((s) => (
              <div
                key={s.band}
                className="grid grid-cols-[90px_1fr] items-center gap-[12px] text-[12.5px]"
              >
                <span className="font-mono text-[12px]">{s.band}</span>
                <span className="relative h-[22px] rounded-[5px] bg-accent-bg">
                  <span
                    className="absolute h-full rounded-[5px] bg-accent opacity-[0.85]"
                    style={{ left: `${s.lo}%`, width: `${s.hi - s.lo}%` }}
                  />
                </span>
              </div>
            ))}
          </div>
          <p className="mt-[14px] text-[12.5px] leading-[1.5] text-ink-2">
            Only ~38% of ads list pay. Never used to rank or filter — shown for
            context only.
          </p>
        </Panel>

        <Panel title="Most-active companies" sub="postings, 8w">
          <div className="flex flex-col gap-[13px]">
            {ins.activeCompanies.map((c, i) => (
              <div
                key={c.name}
                className="grid grid-cols-[120px_1fr_30px] items-center gap-[12px]"
              >
                <span className="text-[12.5px] font-medium">{c.name}</span>
                <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
                  <span
                    className="block h-full origin-left rounded-[3px] motion-safe:[animation:barGrow_0.9s_cubic-bezier(0.3,1,0.3,1)]"
                    style={{
                      width: `${(c.n / 12) * 100}%`,
                      background: i === 0 ? "var(--accent)" : "var(--ink)",
                    }}
                  />
                </span>
                <span className="text-right font-mono text-[11px] text-ink-2">
                  {c.n}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </section>
  );
}
