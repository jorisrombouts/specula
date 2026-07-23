"use client";

import type { EducationEntry } from "@specula/shared-types";
import { YearSelect } from "@/components/candidate/year-select";
import { ROW_INPUT } from "@/components/candidate/row-styles";

export function EducationEditor({
  value,
  onChange,
}: {
  value: EducationEntry[];
  onChange: (v: EducationEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<EducationEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () =>
    onChange([
      ...value,
      { degree: "", field: "", institution: "", year: null },
    ]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[96px_1fr_1fr_92px_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={ROW_INPUT}
              placeholder="Degree"
              aria-label={`degree ${i + 1}`}
              value={row.degree}
              onChange={(e) => update(i, { degree: e.target.value })}
            />
            <input
              className={ROW_INPUT}
              placeholder="Field"
              aria-label={`field ${i + 1}`}
              value={row.field}
              onChange={(e) => update(i, { field: e.target.value })}
            />
            <input
              className={ROW_INPUT}
              placeholder="Institution"
              aria-label={`institution ${i + 1}`}
              value={row.institution}
              onChange={(e) => update(i, { institution: e.target.value })}
            />
            <YearSelect
              ariaLabel={`year ${i + 1}`}
              value={row.year}
              onChange={(y) => update(i, { year: y })}
            />
            <button
              type="button"
              aria-label={`remove education ${i + 1}`}
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
        + add education
      </button>
    </div>
  );
}
