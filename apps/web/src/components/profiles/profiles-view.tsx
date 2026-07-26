"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { LensSummary } from "@specula/shared-types";
import { Toggle } from "@/components/atoms/toggle";
import { Button } from "@/components/atoms/button";
import { LensEditor } from "@/components/profiles/lens-editor";
import { originLabel, parseScope } from "@/lib/lens-catalog";
import {
  createLens,
  deleteLens,
  updateLens,
  type LensPatch,
} from "@/lib/api/lenses";

const scopeLabel = (scope: string): string => {
  const p = parseScope(scope);
  return p.type === "Any" ? "Any region" : `${p.type} · ${p.value}`;
};

function Rule({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div>
      <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
        {label}
      </div>
      <div className={`text-[13px] ${muted ? "text-ink-2" : "text-ink"}`}>
        {value}
      </div>
    </div>
  );
}

type Row = { lens: LensSummary; editing: boolean; isNew: boolean; key: string };
let tmp = 0;

export function ProfilesView({ lenses: seed }: { lenses: LensSummary[] }) {
  const router = useRouter();
  const defaults = seed.filter((l) => l.isDefault);
  const [rows, setRows] = useState<Row[]>(() =>
    seed
      .filter((l) => !l.isDefault)
      .map((l) => ({ lens: l, editing: false, isNew: false, key: l.id })),
  );

  const activeN =
    defaults.filter((l) => l.active).length +
    rows.filter((r) => r.lens.active).length;
  const totalN = defaults.length + rows.length;

  const setRow = (key: string, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const addNew = () => {
    const key = `new-${tmp++}`;
    const blank: LensSummary = {
      id: key,
      name: "",
      short: "",
      active: true,
      scope: "",
      modes: ["Remote"],
      origin: "",
      focus: "",
      seeds: [],
      count: 0,
      isNew: 0,
      isDefault: false,
    };
    setRows((rs) => [...rs, { lens: blank, editing: true, isNew: true, key }]);
  };

  const cancel = (row: Row) =>
    row.isNew
      ? setRows((rs) => rs.filter((r) => r.key !== row.key))
      : setRow(row.key, { editing: false });

  // After each lens mutation, drop this route's cached RSC payload — Next reuses it verbatim on
  // browser back/forward, so without this a save→leave→Back round-trip re-renders stale lenses.
  const save = async (row: Row, patch: LensPatch) => {
    if (row.isNew) {
      const created = await createLens(patch);
      setRows((rs) =>
        rs.map((r) =>
          r.key === row.key
            ? { lens: created, editing: false, isNew: false, key: created.id }
            : r,
        ),
      );
    } else {
      const updated = await updateLens(row.lens.id, patch);
      setRow(row.key, { lens: updated, editing: false });
    }
    router.refresh();
  };

  const remove = async (row: Row) => {
    if (!row.isNew) await deleteLens(row.lens.id);
    setRows((rs) => rs.filter((r) => r.key !== row.key));
    router.refresh();
  };

  const toggle = async (row: Row) => {
    const active = !row.lens.active;
    setRow(row.key, { lens: { ...row.lens, active } });
    await updateLens(row.lens.id, { active });
    router.refresh();
  };

  return (
    <section
      data-screen-label="profiles"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Search profiles
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Named lenses over one shared pool. Each{" "}
            <b>owns geography &amp; work mode entirely</b> — location scope,
            allowed modes, and HQ-origin rule — layered over your global
            targeting baseline. A role can match several at once; switching a
            lens re-scopes the Jobs view.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{activeN}</b>{" "}
            active
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{totalN}</b> total
          </div>
        </div>
      </header>

      <div className="mt-[22px] flex flex-col gap-[13px]">
        {rows.map((row) =>
          row.editing ? (
            <LensEditor
              key={row.key}
              lens={row.lens}
              isNew={row.isNew}
              onSave={(p) => save(row, p)}
              onCancel={() => cancel(row)}
              onDelete={() => remove(row)}
            />
          ) : (
            <div
              key={row.key}
              data-lens={row.lens.id}
              data-active={row.lens.active}
              className={`rounded-[14px] border border-rule bg-card p-[18px_22px] shadow-card transition-colors hover:border-rule-2 ${row.lens.active ? "" : "opacity-60"}`}
            >
              <div className="mb-[14px] flex items-center gap-[14px]">
                <span className="font-display text-[19px] font-semibold">
                  {row.lens.name}
                </span>
                <span className="font-mono text-[10px] text-ink-2">
                  {row.lens.count} roles · {row.lens.isNew} new
                </span>
                <span className="ml-auto flex items-center gap-[14px]">
                  <button
                    type="button"
                    onClick={() => setRow(row.key, { editing: true })}
                    className="cursor-pointer border-none bg-transparent font-mono text-[10.5px] uppercase tracking-[0.06em] text-ink-2 hover:text-ink"
                  >
                    Edit
                  </button>
                  <Toggle on={row.lens.active} onChange={() => toggle(row)} />
                </span>
              </div>
              <div className="grid grid-cols-3 gap-[16px]">
                <Rule
                  label="Location scope · hard"
                  value={scopeLabel(row.lens.scope)}
                />
                <Rule
                  label="Work mode · hard"
                  value={row.lens.modes.join(" / ") || "—"}
                />
                <Rule
                  label="Origin rule · hard"
                  value={originLabel(row.lens.origin)}
                />
              </div>
              <div className="mt-[16px] grid grid-cols-2 gap-[16px]">
                <Rule
                  label="Focus · soft signal"
                  value={row.lens.focus || "—"}
                  muted
                />
                <div>
                  <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
                    Discovery seeds
                  </div>
                  <div className="mt-[6px] flex flex-wrap gap-[6px]">
                    {row.lens.seeds.map((s) => (
                      <span
                        key={s}
                        className="rounded-[5px] bg-panel px-[8px] py-[3px] font-mono text-[10.5px] text-ink-2"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ),
        )}
      </div>
      <Button className="mt-[16px]" onClick={addNew}>
        + New profile
      </Button>
    </section>
  );
}
