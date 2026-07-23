"use client";

import type { Mode } from "@specula/shared-types";
import { WORK_MODES } from "@specula/shared-types";

export function ModeSelect({
  value,
  onChange,
}: {
  value: Mode[];
  onChange: (v: Mode[]) => void;
}) {
  const toggle = (m: Mode) =>
    onChange(value.includes(m) ? value.filter((x) => x !== m) : [...value, m]);

  return (
    <div className="flex flex-wrap gap-2">
      {WORK_MODES.map((m) => {
        const on = value.includes(m);
        return (
          <button
            key={m}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(m)}
            className={`rounded-[8px] border px-[15px] py-[10px] text-[12.5px] transition-colors ${
              on
                ? "border-ink bg-ink text-paper"
                : "border-rule-2 bg-panel text-ink hover:border-ink"
            }`}
          >
            {m}
          </button>
        );
      })}
    </div>
  );
}
