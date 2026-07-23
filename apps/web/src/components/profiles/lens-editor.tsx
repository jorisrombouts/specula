"use client";

import { useState } from "react";
import type { Mode } from "@specula/shared-types";
import { WORK_MODES } from "@specula/shared-types";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Field } from "@/components/config/field";
import { Button } from "@/components/atoms/button";
import {
  COUNTRIES,
  ORIGIN_OPTIONS,
  REGIONS,
  SCOPE_TYPES,
  parseScope,
  serializeScope,
  type ScopeParts,
  type ScopeType,
} from "@/lib/lens-catalog";
import type { LensPatch } from "@/lib/api/lenses";

const INPUT =
  "w-full rounded-[8px] border border-rule-2 bg-card px-[10px] py-[8px] font-body text-[13px] text-ink focus:border-ink focus:outline-none";

type EditableLens = {
  name: string;
  scope: string;
  modes: Mode[];
  origin: string;
  focus: string;
  seeds: string[];
  active: boolean;
};

export function LensEditor({
  lens,
  isNew = false,
  onSave,
  onCancel,
  onDelete,
}: {
  lens: EditableLens;
  isNew?: boolean;
  onSave: (patch: LensPatch) => void;
  onCancel: () => void;
  onDelete: () => void;
}) {
  const [name, setName] = useState(lens.name);
  const [scope, setScope] = useState<ScopeParts>(() => parseScope(lens.scope));
  const [modes, setModes] = useState<Mode[]>(lens.modes);
  const [origin, setOrigin] = useState(lens.origin);
  const [focus, setFocus] = useState(lens.focus);
  const [seeds, setSeeds] = useState<string[]>(lens.seeds);

  const patch = (): LensPatch => ({
    name: name.trim(),
    short: name.trim(),
    scope: serializeScope(scope),
    modes,
    origin,
    focus,
    seeds,
    active: lens.active,
  });

  // Dirty via one serialized snapshot captured once (lazy initial state). JSON of the array
  // is collision-free — unlike join(), where a comma inside a seed/focus value could hide a
  // real edit and wrongly disable Save.
  const snapshot = (): string =>
    JSON.stringify([name, scope, modes, origin, focus, seeds]);
  const [initialSnapshot] = useState(snapshot);
  const dirty = snapshot() !== initialSnapshot;
  const canSave = name.trim() !== "" && (isNew || dirty);

  const setScopeType = (type: ScopeType) => {
    let value = scope.value;
    if (type === "Any") value = "";
    else if (type === "Region" && !REGIONS.includes(value)) value = REGIONS[0];
    else if (type === "Country" && !COUNTRIES.some(([c]) => c === value))
      value = COUNTRIES[0][0];
    else if (
      type === "City" &&
      (REGIONS.includes(value) || /^[A-Z]{2}$/.test(value))
    )
      value = "";
    setScope({ type, value });
  };

  return (
    <div
      data-lens-edit
      className="rounded-[14px] border border-accent bg-card p-[18px_22px] shadow-card"
    >
      <div className="mb-[14px] flex items-center gap-[14px]">
        <input
          aria-label="profile name"
          className="min-w-[220px] rounded-[8px] border border-rule-2 bg-card px-[11px] py-[7px] font-display text-[18px] font-semibold text-ink focus:border-ink focus:outline-none"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Profile name"
        />
      </div>

      <div className="grid grid-cols-3 gap-[16px]">
        <Field label="Location scope · hard">
          <div className="flex gap-2">
            <select
              aria-label="scope type"
              className={`${INPUT} w-[104px] flex-none`}
              value={scope.type}
              onChange={(e) => setScopeType(e.target.value as ScopeType)}
            >
              {SCOPE_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            {scope.type === "Any" ? (
              <span className="self-center pl-1 text-[12px] text-ink-2">
                no location filter
              </span>
            ) : scope.type === "Region" ? (
              <select
                aria-label="scope value"
                className={`${INPUT} flex-1`}
                value={scope.value}
                onChange={(e) =>
                  setScope({ type: "Region", value: e.target.value })
                }
              >
                {REGIONS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            ) : scope.type === "Country" ? (
              <select
                aria-label="scope value"
                className={`${INPUT} flex-1`}
                value={scope.value}
                onChange={(e) =>
                  setScope({ type: "Country", value: e.target.value })
                }
              >
                {COUNTRIES.map(([c, n]) => (
                  <option key={c} value={c}>
                    {n} ({c})
                  </option>
                ))}
              </select>
            ) : (
              <input
                aria-label="scope value"
                className={`${INPUT} flex-1`}
                placeholder="City, CC — e.g. Berlin, DE"
                value={scope.value}
                onChange={(e) =>
                  setScope({ type: "City", value: e.target.value })
                }
              />
            )}
          </div>
        </Field>
        <Field label="Work mode · hard">
          <ChipMultiSelect
            options={WORK_MODES}
            value={modes}
            onChange={setModes}
          />
        </Field>
        <Field label="Origin rule · hard">
          <select
            aria-label="origin rule"
            className={INPUT}
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          >
            {ORIGIN_OPTIONS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="mt-[8px] grid grid-cols-2 gap-[16px]">
        <Field label="Focus · soft signal">
          <input
            aria-label="focus"
            className={INPUT}
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="soft preference, e.g. async-first teams"
          />
        </Field>
        <Field label="Discovery seeds · editable">
          <TagEditor values={seeds} onChange={setSeeds} />
        </Field>
      </div>

      <div className="mt-[16px] flex items-center gap-[10px] border-t border-rule pt-[15px]">
        <Button
          variant="pri"
          disabled={!canSave}
          onClick={() => onSave(patch())}
        >
          Save profile
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
        {dirty && (
          <span className="font-mono text-[11px] text-warn">
            Unsaved changes
          </span>
        )}
        <button
          type="button"
          onClick={onDelete}
          className="ml-auto rounded-[8px] border border-transparent px-[13px] py-2 text-[12.5px] text-warn hover:bg-warn-bg"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
