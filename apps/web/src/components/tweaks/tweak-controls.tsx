export function Segmented({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      <div
        role="radiogroup"
        className="flex gap-[2px] rounded-[8px] bg-panel-2 p-[2px]"
      >
        {options.map((o) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={o === value}
            aria-label={o}
            onClick={() => onChange(o)}
            className={`flex-1 rounded-[6px] px-[6px] py-[4px] text-[11.5px] font-medium capitalize motion-safe:transition-colors ${
              o === value
                ? "bg-card text-ink shadow-card"
                : "text-ink-2 hover:text-ink"
            }`}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SelectControl({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-[28px] rounded-[7px] border border-rule-2 bg-card px-[8px] text-[12px] text-ink"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

export function ColorChips({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      <div role="radiogroup" className="flex gap-[6px]">
        {options.map((o) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={o === value}
            aria-label={o}
            onClick={() => onChange(o)}
            style={{ background: o }}
            className={`h-[26px] flex-1 rounded-[6px] ${
              o === value
                ? "ring-2 ring-ink ring-offset-1"
                : "ring-1 ring-black/10"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
