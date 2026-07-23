"use client";

import type { ExperienceEntry } from "@specula/shared-types";
import { YearSelect } from "@/components/candidate/year-select";
import { ROW_INPUT } from "@/components/candidate/row-styles";

export function ExperienceEditor({
  value,
  onChange,
}: {
  value: ExperienceEntry[];
  onChange: (v: ExperienceEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<ExperienceEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () =>
    onChange([...value, { role: "", org: "", startYear: null, endYear: null }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[1fr_1fr_96px_96px_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={ROW_INPUT}
              placeholder="Role"
              aria-label={`role ${i + 1}`}
              value={row.role}
              onChange={(e) => update(i, { role: e.target.value })}
            />
            <input
              className={ROW_INPUT}
              placeholder="Organisation"
              aria-label={`org ${i + 1}`}
              value={row.org}
              onChange={(e) => update(i, { org: e.target.value })}
            />
            <YearSelect
              ariaLabel={`start year ${i + 1}`}
              value={row.startYear}
              onChange={(y) => update(i, { startYear: y })}
            />
            <YearSelect
              ariaLabel={`end year ${i + 1}`}
              value={row.endYear}
              presentLabel="Present"
              onChange={(y) => update(i, { endYear: y })}
            />
            <button
              type="button"
              aria-label={`remove role ${i + 1}`}
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
        + add role
      </button>
    </div>
  );
}
