"use client";

import type { LanguageEntry } from "@specula/shared-types";
import { CEFR_LEVELS } from "@specula/shared-types";
import { ROW_INPUT } from "@/components/candidate/row-styles";

export function LanguageEditor({
  value,
  onChange,
}: {
  value: LanguageEntry[];
  onChange: (v: LanguageEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<LanguageEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => onChange([...value, { language: "", level: "Native" }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[1fr_128px_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={ROW_INPUT}
              placeholder="Language"
              aria-label={`language ${i + 1}`}
              value={row.language}
              onChange={(e) => update(i, { language: e.target.value })}
            />
            <select
              className={ROW_INPUT}
              aria-label={`level ${i + 1}`}
              value={row.level}
              onChange={(e) =>
                update(i, { level: e.target.value as LanguageEntry["level"] })
              }
            >
              {CEFR_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
            <button
              type="button"
              aria-label={`remove language ${i + 1}`}
              onClick={() => remove(i)}
              className="justify-self-center font-mono text-[15px] text-ink-3 hover:text-warn"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={add}
        className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
      >
        + add language
      </button>
    </div>
  );
}
