import type { LensSummary } from "@specula/shared-types";

export function LensBar({
  lenses,
  active,
  onSelect,
}: {
  lenses: LensSummary[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="mt-[18px] flex overflow-hidden rounded-[8px] border border-rule-2 bg-card">
      {lenses.map((l) => {
        const on = l.id === active;
        return (
          <button
            key={l.id}
            onClick={() => onSelect(l.id)}
            className={`flex min-w-0 flex-1 flex-col gap-[4px] border-r border-rule px-[14px] py-[11px] text-left transition-colors last:border-r-0 ${
              on ? "bg-ink" : "hover:bg-panel"
            }`}
          >
            <span
              className={`flex items-center gap-[6px] text-[13px] font-semibold ${
                on ? "text-paper" : "text-ink"
              }`}
            >
              {l.short}
              {l.isNew > 0 && (
                <span
                  className={`h-[6px] w-[6px] rounded-full ${on ? "bg-[#7FD3A0]" : "bg-accent"}`}
                />
              )}
            </span>
            <span
              className={`font-mono text-[10px] ${on ? "text-[rgba(251,250,246,0.55)]" : "text-ink-2"}`}
            >
              {l.count} roles · {l.isNew} new
            </span>
          </button>
        );
      })}
    </div>
  );
}
