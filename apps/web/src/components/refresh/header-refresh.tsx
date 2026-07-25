"use client";

// Option B page-header refresh control: a solid primary button with a small status line
// beneath it. Presentational only — the Jobs and Companies headers supply the label, the
// click handler, and the status/error text for their own operation.
export function HeaderRefresh({
  label,
  busyLabel,
  busy,
  onClick,
  status,
  warn = false,
}: {
  label: string;
  busyLabel: string;
  busy: boolean;
  onClick: () => void;
  status: string | null;
  warn?: boolean;
}) {
  return (
    <div className="flex flex-col items-end gap-[6px]">
      <button
        type="button"
        disabled={busy}
        onClick={onClick}
        className="font-body flex items-center gap-[7px] rounded-[8px] border border-ink bg-ink px-[15px] py-[9px] text-[12.5px] font-semibold text-paper transition-colors hover:bg-black disabled:opacity-60"
      >
        <span aria-hidden className={busy ? "animate-spin" : undefined}>
          ↻
        </span>
        {busy ? busyLabel : label}
      </button>
      {status ? (
        <span
          role={warn ? "alert" : undefined}
          className={`font-mono flex items-center gap-[6px] text-[10.5px] ${warn ? "text-warn" : "text-ink-2"}`}
        >
          {!warn ? (
            <span
              className="h-[6px] w-[6px] rounded-full bg-accent"
              aria-hidden
            />
          ) : null}
          {status}
        </span>
      ) : null}
    </div>
  );
}
