import type { Trend } from "@specula/shared-types";

export function DemandTrend({ trend }: { trend: Trend }) {
  const totals = trend.weeks.map((_, wi) =>
    trend.series.reduce((s, ser) => s + ser.data[wi], 0),
  );
  const max = Math.max(...totals);
  return (
    <div>
      <div className="relative flex h-[150px] items-end gap-0 pt-[10px]">
        {trend.weeks.map((wk, wi) => (
          <div
            key={wk}
            data-trend-col
            className="flex h-full flex-1 flex-col items-center justify-end gap-[8px]"
          >
            <div className="flex h-full w-[60%] flex-col justify-end gap-[2px]">
              {trend.series.map((ser) => (
                <div
                  key={ser.name}
                  className="min-h-[2px] rounded-t-[2px]"
                  style={{
                    background: ser.color,
                    height: `${(ser.data[wi] / max) * 130}px`,
                  }}
                />
              ))}
            </div>
            <span className="font-mono text-[9px] text-ink-3">{wk}</span>
          </div>
        ))}
      </div>
      <div className="mt-[14px] flex gap-[16px] font-mono text-[10.5px] text-ink-2">
        {trend.series.map((s) => (
          <span key={s.name} className="flex items-center gap-[6px]">
            <i
              className="h-[9px] w-[9px] rounded-[2px]"
              style={{ background: s.color }}
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}
