"use client";

import { useState } from "react";
import type { Candidate, SkillsGap } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Button } from "@/components/atoms/button";
import { Field } from "@/components/config/field";

const INPUT =
  "w-full rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] text-ink focus:border-ink focus:outline-none";
const CHIP =
  "mb-2 block rounded-[7px] border border-rule bg-panel px-3 py-[6px] text-[12.5px] text-ink";

export function CandidateView({
  candidate: c,
  skillsGap,
}: {
  candidate: Candidate;
  skillsGap: SkillsGap[];
}) {
  const [skills, setSkills] = useState(c.skills);

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
            <input className={INPUT} defaultValue={c.title} />
          </Field>
          <div className="grid grid-cols-2 gap-[16px]">
            <Field label="Location">
              <input className={INPUT} defaultValue={c.location} />
            </Field>
            <Field label="Work mode">
              <input className={INPUT} defaultValue={c.workMode} />
            </Field>
            <Field label="Years experience">
              <input className={INPUT} defaultValue={`${c.years} years`} />
            </Field>
            <Field label="Visa">
              <input className={INPUT} defaultValue={c.visa} />
            </Field>
          </div>
          <Field label="Skills · matched against required_skills">
            <TagEditor values={skills} onChange={setSkills} />
          </Field>
          <Field label="Projects">
            {c.projects.map((p) => (
              <div
                key={p.name}
                className="mb-2 block rounded-[7px] border border-rule-2 bg-card px-3 py-[6px] text-[12.5px] text-ink"
              >
                <b>{p.name}</b> <span className="text-ink-2">— {p.note}</span>
              </div>
            ))}
          </Field>
          <div className="grid grid-cols-2 gap-[16px]">
            <Field label="Experience">
              {c.experience.map((e) => (
                <div key={e.org} className={CHIP}>
                  <b>{e.role}</b> · {e.org}{" "}
                  <span className="font-mono text-[11px] text-ink-2">
                    {e.period}
                  </span>
                </div>
              ))}
            </Field>
            <Field label="Education & languages">
              <div className={CHIP}>{c.education}</div>
              <div className="flex flex-wrap gap-2">
                {c.languages.map((l) => (
                  <span
                    key={l}
                    className="rounded-[7px] border border-rule bg-panel px-3 py-[6px] text-[12.5px] text-ink"
                  >
                    {l}
                  </span>
                ))}
              </div>
            </Field>
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
            {skillsGap.map((g) => (
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
                <div>
                  <div className="text-[13px] font-semibold">{g.skill}</div>
                  <div className="mt-px font-mono text-[10.5px] text-ink-2">
                    {g.note}
                  </div>
                </div>
                <span className="ml-auto font-mono text-[18px] font-semibold text-warn">
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
