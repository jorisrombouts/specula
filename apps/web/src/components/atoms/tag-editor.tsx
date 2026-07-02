"use client";

import { useState } from "react";

type Kind = "default" | "syn" | "avoid";
const chipCls: Record<Kind, string> = {
  default: "border-rule bg-panel text-ink",
  syn: "border-ink bg-ink text-paper",
  avoid: "border-transparent bg-warn-bg text-warn",
};
const xCls: Record<Kind, string> = {
  default: "text-ink-3",
  syn: "text-[rgba(251,250,246,0.5)]",
  avoid: "text-ink-3",
};

export function TagEditor({
  values,
  onChange,
  kind = "default",
}: {
  values: string[];
  onChange: (v: string[]) => void;
  kind?: Kind;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const commit = () => {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft("");
    setAdding(false);
  };
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((v) => (
        <span
          key={v}
          className={`flex items-center gap-2 rounded-[7px] border px-3 py-[6px] text-[12.5px] ${chipCls[kind]}`}
        >
          {v}
          <button
            type="button"
            aria-label={`remove ${v}`}
            onClick={() => onChange(values.filter((x) => x !== v))}
            className={`font-mono cursor-pointer ${xCls[kind]}`}
          >
            ×
          </button>
        </span>
      ))}
      {adding ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && commit()}
          onBlur={commit}
          className="rounded-[7px] border border-rule-2 bg-card px-3 py-[6px] text-[12.5px] text-ink outline-none focus:border-ink"
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
        >
          + add
        </button>
      )}
    </div>
  );
}
