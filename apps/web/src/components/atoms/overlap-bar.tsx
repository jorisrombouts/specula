export function OverlapBar({ overlap }: { overlap: [number, number] }) {
  const [matched, total] = overlap;
  const low = matched / total < 0.4;
  const pct = (matched / total) * 100;
  return (
    <span
      data-low={low}
      className={`inline-flex items-center gap-[7px] font-medium ${low ? "text-warn" : "text-ink"}`}
    >
      <span className="h-[5px] w-[42px] overflow-hidden rounded-[3px] bg-panel-2">
        <span
          className={`block h-full ${low ? "bg-warn" : "bg-accent"}`}
          style={{ width: `${pct}%` }}
        />
      </span>
      [{matched}/{total}] req. skills
    </span>
  );
}
