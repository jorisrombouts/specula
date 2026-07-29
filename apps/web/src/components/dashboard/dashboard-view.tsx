import type { DashboardSummary, Run } from "@specula/shared-types";

function tokens(n: number): string {
  return n.toLocaleString("en-US");
}

// Tailwind background token per run status (queued/running/done/error).
const STATUS_DOT: Record<Run["status"], string> = {
  queued: "bg-ink-3",
  running: "bg-accent",
  done: "bg-accent",
  error: "bg-warn",
};

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

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] border border-rule bg-card p-[20px_22px] shadow-card">
      <div className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-ink-2">
        {label}
      </div>
      <div className="mt-[10px] font-display text-[34px] font-semibold leading-none tracking-[-0.01em] tabular-nums">
        {value}
      </div>
    </div>
  );
}

function Bar({ frac }: { frac: number }) {
  return (
    <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
      <span
        className="block h-full origin-left rounded-[3px] bg-accent motion-safe:[animation:barGrow_0.9s_cubic-bezier(0.3,1,0.3,1)]"
        style={{ width: `${Math.round(frac * 100)}%` }}
      />
    </span>
  );
}

export function DashboardView({ summary: s }: { summary: DashboardSummary }) {
  const stageMax = Math.max(1, ...s.tokensByStage.map((x) => x.totalTokens));
  const dayMax = Math.max(1, ...s.tokensByDay.map((x) => x.totalTokens));

  return (
    <section
      data-screen-label="dashboard"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Dashboard
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Internal run &amp; usage observability — LLM tokens per stage, per
            day, and the status of recent discovery runs. Read-only.
          </p>
        </div>
      </header>

      <div className="mt-[22px] grid grid-cols-2 gap-[18px]">
        <Tile label="Total LLM tokens" value={tokens(s.totalTokens)} />
        <Tile label="Runs" value={String(s.runCount)} />
      </div>

      <div className="mt-[18px] grid grid-cols-2 gap-[18px]">
        <Panel title="Tokens by stage" sub="tokens · all time">
          {s.tokensByStage.length === 0 ? (
            <p className="text-[12.5px] text-ink-2">No tokens recorded yet.</p>
          ) : (
            <div className="flex flex-col gap-[13px]">
              {s.tokensByStage.map((row) => (
                <div
                  key={row.stage}
                  className="grid grid-cols-[110px_1fr_78px] items-center gap-[12px]"
                >
                  <span className="text-[12.5px] font-medium">{row.stage}</span>
                  <Bar frac={row.totalTokens / stageMax} />
                  <span className="text-right font-mono text-[11px] text-ink-2 tabular-nums">
                    {tokens(row.totalTokens)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Tokens by day" sub="tokens · runs">
          {s.tokensByDay.length === 0 ? (
            <p className="text-[12.5px] text-ink-2">No tokens recorded yet.</p>
          ) : (
            <div className="flex flex-col gap-[13px]">
              {s.tokensByDay.map((row) => (
                <div
                  key={row.date}
                  className="grid grid-cols-[92px_1fr_92px] items-center gap-[12px]"
                >
                  <span className="font-mono text-[11px] text-ink-2">
                    {row.date}
                  </span>
                  <Bar frac={row.totalTokens / dayMax} />
                  <span className="text-right font-mono text-[11px] text-ink-2 tabular-nums">
                    {tokens(row.totalTokens)}
                    <span className="ml-[6px] text-ink-3">· {row.runs}r</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="mt-[18px]">
        <Panel title="Recent runs" sub="newest first">
          {s.recentRuns.length === 0 ? (
            <p className="text-[12.5px] text-ink-2">No runs yet.</p>
          ) : (
            <div className="flex flex-col">
              <div className="grid grid-cols-[1fr_110px_110px_1fr_92px] gap-[12px] border-b border-rule pb-[8px] font-mono text-[10px] uppercase tracking-[0.08em] text-ink-2">
                <span>Created</span>
                <span>Kind</span>
                <span>Status</span>
                <span>Found / new / err</span>
                <span className="text-right">Tokens</span>
              </div>
              {s.recentRuns.map((run) => (
                <div
                  key={run.id}
                  className="grid grid-cols-[1fr_110px_110px_1fr_92px] items-center gap-[12px] border-b border-rule py-[10px] text-[12.5px] last:border-b-0"
                >
                  <span className="font-mono text-[11px] text-ink-2">
                    {run.createdAt.slice(0, 10)}
                  </span>
                  <span className="font-mono text-[11px]">{run.kind}</span>
                  <span className="flex items-center gap-[7px] font-mono text-[11px]">
                    <i
                      className={`h-[7px] w-[7px] rounded-full ${STATUS_DOT[run.status]}`}
                    />
                    {run.status}
                  </span>
                  <span className="font-mono text-[11px] text-ink-2 tabular-nums">
                    {run.stats.found} / {run.stats.new} /{" "}
                    <b
                      className={
                        run.stats.errors > 0 ? "text-warn" : "text-ink-2"
                      }
                    >
                      {run.stats.errors}
                    </b>
                  </span>
                  <span className="text-right font-mono text-[11px] tabular-nums">
                    {run.tokens ? tokens(run.tokens.totalTokens) : "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </section>
  );
}
