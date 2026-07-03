"use client";

import { useState } from "react";
import type { Targeting } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Field } from "@/components/config/field";

export function TargetingView({ targeting: t }: { targeting: Targeting }) {
  const [titles, setTitles] = useState(t.roleTitles);
  const [must, setMust] = useState(t.mustHaves);
  const [avoid, setAvoid] = useState(t.avoid);

  return (
    <section
      data-screen-label="targeting"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Targeting
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Your global baseline — <b>who you are and what you want</b>: role
            identity, seniority, and values. Shared across every lens; drives
            discovery and the role &amp; skill match factors.{" "}
            <b>Geography and work mode live in Search profiles</b>, not here.
          </p>
        </div>
      </header>

      <div className="mt-[24px] max-w-[760px]">
        <Field label="Role titles · synonyms (the field uses many names)">
          <TagEditor kind="syn" values={titles} onChange={setTitles} />
        </Field>
        <Field label="Seniority">
          <div className="flex flex-wrap gap-2">
            {t.seniority.map((s) => (
              <span
                key={s}
                className="rounded-[7px] border border-rule bg-panel px-3 py-[6px] text-[12.5px] text-ink"
              >
                {s}
              </span>
            ))}
          </div>
        </Field>
        <div className="grid grid-cols-2 gap-[24px]">
          <Field label="Must-haves">
            <TagEditor values={must} onChange={setMust} />
          </Field>
          <Field label="Avoid">
            <TagEditor kind="avoid" values={avoid} onChange={setAvoid} />
          </Field>
        </div>
        <Field label="Free-text preferences · fed to the model as soft signal">
          <textarea
            rows={4}
            defaultValue={t.preferences}
            className="min-h-[78px] w-full resize-y rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] leading-[1.55] text-ink focus:border-ink focus:outline-none"
          />
        </Field>
        <div className="flex items-center gap-[12px] rounded-[11px] border border-accent bg-accent-bg px-[18px] py-[13px] text-[13px] text-accent-ink">
          ⓘ{" "}
          <span>
            No geography here, by design — location, work mode and HQ-origin
            rules belong to <b>Search profiles</b> (lenses), so one identity can
            be viewed through many regional searches. Salary is likewise never a
            rule or signal; it&apos;s shown only when an ad states it.
          </span>
        </div>
      </div>
    </section>
  );
}
