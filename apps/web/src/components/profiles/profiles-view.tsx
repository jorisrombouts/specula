"use client";

import { useState } from "react";
import type { LensSummary } from "@specula/shared-types";
import { Toggle } from "@/components/atoms/toggle";
import { Button } from "@/components/atoms/button";

function RuleItem({
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

export function ProfilesView({ lenses: seed }: { lenses: LensSummary[] }) {
  const [lenses, setLenses] = useState(seed);
  const toggle = (id: string) =>
    setLenses((ls) =>
      ls.map((l) => (l.id === id ? { ...l, active: !l.active } : l)),
    );
  const active = lenses.filter((l) => l.active).length;
  const cards = lenses.filter((l) => l.id !== "all");

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
            lens re-scopes the Jobs view and re-scores it on location.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{active}</b>{" "}
            active
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">
              {lenses.length}
            </b>{" "}
            total
          </div>
        </div>
      </header>

      <div className="mt-[22px] flex flex-col gap-[13px]">
        {cards.map((l) => (
          <div
            key={l.id}
            data-lens={l.id}
            data-active={l.active}
            className={`rounded-[14px] border border-rule bg-card p-[18px_22px] shadow-card transition-colors hover:border-rule-2 ${l.active ? "" : "opacity-60"}`}
          >
            <div className="mb-[14px] flex items-center gap-[14px]">
              <span className="font-display text-[19px] font-semibold">
                {l.name}
              </span>
              <span className="font-mono text-[10px] text-ink-2">
                {l.count} roles · {l.isNew} new
              </span>
              <span className="ml-auto">
                <Toggle on={l.active} onChange={() => toggle(l.id)} />
              </span>
            </div>
            <div className="grid grid-cols-3 gap-[16px]">
              <RuleItem label="Location scope · hard" value={l.scope} />
              <RuleItem label="Work mode · hard" value={l.modes.join(" / ")} />
              <RuleItem label="Origin rule · hard" value={l.origin} />
            </div>
            <div className="mt-[16px] grid grid-cols-2 gap-[16px]">
              <RuleItem
                label="Focus · soft signal"
                value={l.focus || "—"}
                muted
              />
              <div>
                <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
                  Discovery seeds · auto
                </div>
                <div className="mt-[6px] flex flex-wrap gap-[6px]">
                  {l.seeds.map((s) => (
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
        ))}
      </div>
      <Button className="mt-[16px]">+ New profile</Button>
    </section>
  );
}
