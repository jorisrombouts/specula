"use client";

import type { ProjectEntry } from "@specula/shared-types";
import { ROW_INPUT } from "@/components/candidate/row-styles";

export function ProjectEditor({
  value,
  onChange,
}: {
  value: ProjectEntry[];
  onChange: (v: ProjectEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<ProjectEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => onChange([...value, { name: "", note: "" }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[210px_1fr_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={ROW_INPUT}
              placeholder="Project name"
              aria-label={`project name ${i + 1}`}
              value={row.name}
              onChange={(e) => update(i, { name: e.target.value })}
            />
            <input
              className={ROW_INPUT}
              placeholder="One-line note"
              aria-label={`project note ${i + 1}`}
              value={row.note}
              onChange={(e) => update(i, { note: e.target.value })}
            />
            <button
              type="button"
              aria-label={`remove project ${i + 1}`}
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
        + add project
      </button>
    </div>
  );
}
