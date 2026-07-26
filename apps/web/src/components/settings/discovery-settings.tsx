"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/button";
import { saveDiscoverySettings } from "@/lib/api/discovery-settings";

// The per-run discovery search cap — how many web searches "Find new companies" fires. The hint
// makes the cost/time tradeoff visible (rough figures from measured ~$0.02 & ~7s per search).
export function DiscoverySettings({ initial }: { initial: number }) {
  const [value, setValue] = useState(initial);
  const [baseline, setBaseline] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = value !== baseline;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveDiscoverySettings(value);
      setBaseline(value);
      setJustSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-[11px] border border-rule-2 bg-card p-[20px]">
      <h2 className="m-0 font-display text-[18px] font-semibold tracking-[-0.01em]">
        Discovery
      </h2>
      <p className="mt-[6px] mb-[16px] max-w-[60ch] text-[13px] text-ink-2">
        How many web searches “Find new companies” runs each time. Fewer is
        cheaper and faster; more finds more companies per run.
      </p>

      <div className="flex items-center gap-[16px]">
        <input
          type="range"
          min={1}
          max={20}
          value={value}
          aria-label="discovery searches per run"
          onChange={(e) => {
            setValue(Number(e.target.value));
            setJustSaved(false);
          }}
          className="w-[240px] accent-accent"
        />
        <span className="font-mono text-[13px] font-semibold text-ink">
          {value} search{value === 1 ? "" : "es"}
        </span>
        <span className="font-mono text-[11px] text-ink-3">
          ≈ ${(0.02 * value).toFixed(2)} · ~{value * 7}s per run
        </span>
      </div>

      <div className="mt-[16px] flex items-center gap-[12px]">
        <Button variant="pri" onClick={save} disabled={saving || !dirty}>
          {saving ? "Saving…" : "Save"}
        </Button>
        {!dirty && justSaved ? (
          <span className="text-[12.5px] text-ink-2">Saved.</span>
        ) : null}
        {error ? (
          <span role="alert" className="font-mono text-[11.5px] text-warn">
            {error}
          </span>
        ) : null}
      </div>
    </div>
  );
}
