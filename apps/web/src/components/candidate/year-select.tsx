"use client";

const MAX_YEAR = new Date().getFullYear() + 1;
const YEARS = Array.from(
  { length: MAX_YEAR - 1950 + 1 },
  (_, i) => MAX_YEAR - i,
);

export function YearSelect({
  value,
  onChange,
  ariaLabel,
  presentLabel,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  ariaLabel: string;
  presentLabel?: string;
}) {
  return (
    <select
      aria-label={ariaLabel}
      value={value === null ? "" : String(value)}
      onChange={(e) =>
        onChange(e.target.value === "" ? null : Number(e.target.value))
      }
      className="w-full rounded-[6px] border border-rule bg-paper px-[8px] py-[8px] text-[12.5px] text-ink focus:border-ink focus:outline-none"
    >
      <option value="">{presentLabel ?? "—"}</option>
      {YEARS.map((y) => (
        <option key={y} value={String(y)}>
          {y}
        </option>
      ))}
    </select>
  );
}
