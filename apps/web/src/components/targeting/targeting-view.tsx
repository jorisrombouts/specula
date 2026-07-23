"use client";

import { useMemo, useState } from "react";
import type { Targeting } from "@specula/shared-types";
import { SENIORITY_LEVELS } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Button } from "@/components/atoms/button";
import { Field } from "@/components/config/field";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";
import { ROLE_TITLES } from "@/lib/role-titles-catalog";
import { saveTargeting, type TargetingPatch } from "@/lib/api/targeting";

export function TargetingView({ targeting: t }: { targeting: Targeting }) {
  const [form, setForm] = useState<TargetingPatch>(t);
  const [baseline, setBaseline] = useState<TargetingPatch>(t);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(baseline),
    [form, baseline],
  );
  const set = <K extends keyof TargetingPatch>(k: K, v: TargetingPatch[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setJustSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveTargeting(form);
      setBaseline(form);
      setJustSaved(true);
    } finally {
      setSaving(false);
    }
  };

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
          <TagEditor
            kind="syn"
            values={form.roleTitles}
            onChange={(v) => set("roleTitles", v)}
            suggestions={ROLE_TITLES}
          />
        </Field>
        <Field label="Seniority">
          <ChipMultiSelect
            options={SENIORITY_LEVELS}
            value={form.seniority}
            onChange={(v) => set("seniority", v)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-[24px]">
          <Field label="Must-haves">
            <TagEditor
              values={form.mustHaves}
              onChange={(v) => set("mustHaves", v)}
            />
          </Field>
          <Field label="Avoid">
            <TagEditor
              kind="avoid"
              values={form.avoid}
              onChange={(v) => set("avoid", v)}
            />
          </Field>
        </div>
        <Field label="Free-text preferences · fed to the model as soft signal">
          <textarea
            rows={4}
            value={form.preferences}
            onChange={(e) => set("preferences", e.target.value)}
            className="min-h-[78px] w-full resize-y rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] leading-[1.55] text-ink focus:border-ink focus:outline-none"
          />
        </Field>

        <div className="mb-[20px] flex items-center gap-[12px]">
          <Button
            variant="pri"
            onClick={handleSave}
            disabled={saving || !dirty}
          >
            {saving ? "Saving…" : "Save targeting"}
          </Button>
          {dirty && (
            <span className="font-mono text-[11.5px] text-warn">
              Unsaved changes
            </span>
          )}
          {!dirty && justSaved && (
            <span className="text-[12.5px] text-ink-2">Saved.</span>
          )}
        </div>

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
