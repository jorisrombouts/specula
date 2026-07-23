"use client";

export function ChipMultiSelect<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T[];
  onChange: (v: T[]) => void;
}) {
  const toggle = (o: T) =>
    onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o]);

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button
            key={o}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(o)}
            className={`rounded-[8px] border px-[15px] py-[10px] text-[12.5px] transition-colors ${
              on
                ? "border-ink bg-ink text-paper"
                : "border-rule-2 bg-panel text-ink hover:border-ink"
            }`}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}
