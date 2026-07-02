"use client";

import { useState } from "react";
import { jobs } from "@/lib/seed/data";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Chip } from "@/components/atoms/chip";
import { Tag } from "@/components/atoms/tag";
import { Button } from "@/components/atoms/button";
import { Toggle } from "@/components/atoms/toggle";
import { TagEditor } from "@/components/atoms/tag-editor";

export default function PreviewPage() {
  const top = jobs.find((j) => j.id === "j1")!;
  const flagged = jobs.find((j) => j.id === "j5")!;
  const [on, setOn] = useState(true);
  const [tags, setTags] = useState(["Python", "RAG"]);
  return (
    <main className="min-h-screen bg-paper p-10 text-ink">
      <h1 className="font-display mb-8 text-[28px] font-semibold">
        Atom preview
      </h1>

      <p className="font-mono mb-4 text-[10px] uppercase tracking-widest text-ink-3">
        MatchMeter
      </p>
      <section className="flex flex-wrap gap-10">
        <MatchMeter job={top} mstyle="bars" />
        <MatchMeter job={top} mstyle="figure" />
        <MatchMeter job={top} mstyle="ring" />
        <MatchMeter job={flagged} mstyle="bars" />
        <MatchMeter job={flagged} mstyle="figure" />
        <MatchMeter job={flagged} mstyle="ring" />
      </section>

      <p className="font-mono mb-4 mt-10 text-[10px] uppercase tracking-widest text-ink-3">
        OverlapBar
      </p>
      <section className="flex flex-col gap-4">
        <OverlapBar overlap={[8, 9]} />
        <OverlapBar overlap={[2, 8]} />
      </section>

      <p className="font-mono mb-4 mt-10 text-[10px] uppercase tracking-widest text-ink-3">
        Chip / Tag
      </p>
      <section className="flex flex-wrap gap-2">
        <Chip>chip</Chip>
        <Chip mono>mono-chip</Chip>
        <Tag variant="new">NEW</Tag>
        <Tag variant="status">Saved</Tag>
        <Tag variant="flag">⚑ red flag</Tag>
      </section>

      <p className="font-mono mb-4 mt-10 text-[10px] uppercase tracking-widest text-ink-3">
        Button
      </p>
      <section className="flex flex-wrap gap-2">
        <Button>Default</Button>
        <Button variant="pri">Primary</Button>
        <Button variant="accent">Accent</Button>
        <Button variant="ghost">Ghost</Button>
      </section>

      <p className="font-mono mb-4 mt-10 text-[10px] uppercase tracking-widest text-ink-3">
        Toggle
      </p>
      <section>
        <Toggle on={on} onChange={setOn} />
      </section>

      <p className="font-mono mb-4 mt-10 text-[10px] uppercase tracking-widest text-ink-3">
        TagEditor
      </p>
      <section className="flex flex-col gap-4">
        <TagEditor values={tags} onChange={setTags} />
        <TagEditor values={["Data Scientist"]} onChange={() => {}} kind="syn" />
        <TagEditor
          values={["Relocation required"]}
          onChange={() => {}}
          kind="avoid"
        />
      </section>
    </main>
  );
}
