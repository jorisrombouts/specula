"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Candidate, SkillsGap, Visa } from "@specula/shared-types";
import { VISA_OPTIONS } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Button } from "@/components/atoms/button";
import { Field } from "@/components/config/field";
import { ModeSelect } from "@/components/candidate/mode-select";
import { LanguageEditor } from "@/components/candidate/language-editor";
import { EducationEditor } from "@/components/candidate/education-editor";
import { ProjectEditor } from "@/components/candidate/project-editor";
import { ExperienceEditor } from "@/components/candidate/experience-editor";
import { COMMON_SKILLS } from "@/lib/skills-catalog";
import { saveCandidate, type CandidatePatch } from "@/lib/api/candidate";
import { RescoreButton } from "@/components/candidate/rescore-button";

const INPUT =
  "w-full rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] text-ink focus:border-ink focus:outline-none";

export function CandidateView({
  candidate: c,
  skillsGap,
}: {
  candidate: Candidate;
  skillsGap: SkillsGap[];
}) {
  const initial: CandidatePatch = useMemo(
    () => ({
      title: c.title,
      location: c.location,
      workMode: c.workMode,
      visa: c.visa,
      years: c.years,
      education: c.education,
      languages: c.languages,
      skills: c.skills,
      projects: c.projects,
      experience: c.experience,
    }),
    [c],
  );

  const router = useRouter();
  const [form, setForm] = useState<CandidatePatch>(initial);
  const [baseline, setBaseline] = useState<CandidatePatch>(initial);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(baseline),
    [form, baseline],
  );

  const set = <K extends keyof CandidatePatch>(k: K, v: CandidatePatch[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setJustSaved(false);
  };

  const hasSkill = (s: string) =>
    form.skills.some((x) => x.toLowerCase() === s.toLowerCase());
  const visibleGap = skillsGap.filter((g) => !hasSkill(g.skill));

  // `PUT /candidate` is a full replace, so every save sends the whole form.
  const persist = async (next: CandidatePatch) => {
    setSaving(true);
    try {
      await saveCandidate(next);
      setBaseline(next);
      setJustSaved(true);
      // Drop this route's cached RSC payload. Next reuses it verbatim on browser
      // back/forward (unlike a <Link> nav, which refetches), so without this a
      // save→leave→Back round-trip re-renders the stale pre-save profile.
      router.refresh();
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => persist(form);

  // The gap row disappearing reads as "added", so make the click actually add it:
  // save straight away rather than staging behind the Save button. On failure the
  // optimistic change is rolled back so the row reappears instead of lying.
  const addGapSkill = async (skill: string) => {
    const prev = form;
    const next = { ...form, skills: [...form.skills, skill] };
    setForm(next);
    try {
      await persist(next);
    } catch {
      setForm(prev);
    }
  };

  return (
    <section
      data-screen-label="candidate"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Candidate profile
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Who you are — fed to the model so every match reflects fit between
            you and the role. Kept explicit (a form, not a parsed CV) so you
            control exactly what you match against. Also powers skills-gap.
          </p>
        </div>
        <div className="flex h-[40px] w-[40px] items-center justify-center rounded-[9px] bg-ink font-mono text-[13px] font-semibold text-paper">
          {c.initials}
        </div>
      </header>

      <div className="mt-[24px] grid grid-cols-[1fr_320px] items-start gap-[26px]">
        <div>
          <Field label="Headline">
            <input
              className={INPUT}
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-2 gap-[16px]">
            <Field label="Location">
              <input
                className={INPUT}
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
              />
            </Field>
            <Field label="Work mode">
              <ModeSelect
                value={form.workMode}
                onChange={(v) => set("workMode", v)}
              />
            </Field>
            <Field label="Years experience">
              <input
                className={INPUT}
                type="number"
                min={0}
                value={form.years}
                onChange={(e) => set("years", Number(e.target.value))}
              />
            </Field>
            <Field label="Visa">
              <select
                className={INPUT}
                value={form.visa}
                onChange={(e) => set("visa", e.target.value as Visa | "")}
              >
                <option value="">— select —</option>
                {VISA_OPTIONS.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Skills · matched against required_skills">
            <TagEditor
              values={form.skills}
              onChange={(v) => set("skills", v)}
              suggestions={COMMON_SKILLS}
            />
          </Field>

          <Field label="Projects">
            <ProjectEditor
              value={form.projects}
              onChange={(v) => set("projects", v)}
            />
          </Field>

          <Field label="Experience">
            <ExperienceEditor
              value={form.experience}
              onChange={(v) => set("experience", v)}
            />
          </Field>

          <Field label="Education">
            <EducationEditor
              value={form.education}
              onChange={(v) => set("education", v)}
            />
          </Field>

          <Field label="Languages">
            <LanguageEditor
              value={form.languages}
              onChange={(v) => set("languages", v)}
            />
          </Field>

          <div className="mt-[18px] flex items-center gap-[12px]">
            <Button
              variant="pri"
              onClick={handleSave}
              disabled={saving || !dirty}
            >
              {saving ? "Saving…" : "Save profile"}
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

          <div className="mt-[16px] border-t border-rule pt-[16px]">
            <p className="mb-[9px] max-w-[54ch] text-[12px] leading-[1.5] text-ink-2">
              Match scores are set when a company is approved. After editing
              your profile or targeting, re-score existing jobs to apply the
              change.
            </p>
            <RescoreButton />
          </div>
        </div>

        <div className="sticky top-0">
          <div className="rounded-[14px] border border-rule bg-card p-[20px_22px] shadow-card">
            <div className="mb-[18px] flex items-baseline justify-between">
              <span className="font-display text-[17px] font-semibold">
                Skills gap
              </span>
              <span className="font-mono text-[10.5px] text-ink-2">
                vs target roles
              </span>
            </div>
            <p className="mb-[6px] text-[12.5px] leading-[1.5] text-ink-2">
              Most-demanded skills across your target roles that aren&apos;t on
              your profile:
            </p>
            {visibleGap.map((g) => (
              <div
                key={g.skill}
                className="flex items-center gap-[11px] border-b border-rule py-[11px] last:border-b-0"
              >
                <span className="flex h-[38px] w-[42px] items-end gap-[2px]">
                  {[40, 70, 55].map((h, i) => (
                    <i
                      key={i}
                      className="flex-1 rounded-[1px] bg-warn opacity-[0.85]"
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold">{g.skill}</div>
                  <div className="mt-px font-mono text-[10.5px] text-ink-2">
                    {g.note}
                  </div>
                </div>
                <button
                  type="button"
                  aria-label={`add ${g.skill} to skills`}
                  onClick={() => addGapSkill(g.skill)}
                  disabled={saving}
                  className="rounded-[7px] border border-rule-2 bg-card px-[9px] py-[5px] text-[11px] text-accent-ink hover:border-accent hover:bg-accent-bg disabled:opacity-50"
                >
                  + add
                </button>
                <span className="font-mono text-[18px] font-semibold text-warn">
                  {g.roles}×
                </span>
              </div>
            ))}
            <Button className="mt-[16px] w-full justify-center">
              ✎ Draft a tailored CV bullet
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
