"use client";

import { useState } from "react";
import { useTweaks } from "@/lib/tweaks";
import { ACCENT_OPTIONS, FONT_OPTIONS } from "@/lib/tweaks-init";
import {
  Segmented,
  SelectControl,
  ColorChips,
} from "@/components/tweaks/tweak-controls";

export function TweaksPanel() {
  const { tweaks, setTweak } = useTweaks();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        aria-label="Tweaks"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 right-4 z-50 flex h-[38px] w-[38px] items-center justify-center rounded-full border border-rule-2 bg-paper/85 text-[16px] text-ink shadow-pop backdrop-blur"
      >
        ⚙
      </button>

      {open && (
        <div className="fixed bottom-[60px] right-4 z-50 flex w-[280px] flex-col rounded-[14px] border border-rule-2 bg-paper/90 shadow-pop backdrop-blur">
          <div className="flex items-center justify-between border-b border-rule px-[14px] py-[10px]">
            <b className="text-[12px] font-semibold">Tweaks</b>
            <button
              type="button"
              aria-label="Close tweaks"
              onClick={() => setOpen(false)}
              className="flex h-[22px] w-[22px] items-center justify-center rounded-[6px] text-ink-2 hover:bg-black/[0.06] hover:text-ink"
            >
              ✕
            </button>
          </div>
          <div className="flex flex-col gap-[12px] px-[14px] py-[12px]">
            <div className="font-mono text-[10px] uppercase tracking-[0.06em] text-ink-3">
              Signature
            </div>
            <Segmented
              label="Match score"
              value={tweaks.mstyle}
              options={["bars", "figure", "ring"]}
              onChange={(v) => setTweak("mstyle", v as typeof tweaks.mstyle)}
            />
            <Segmented
              label="Job layout"
              value={tweaks.layout}
              options={["rows", "cards"]}
              onChange={(v) => setTweak("layout", v as typeof tweaks.layout)}
            />
            <div className="font-mono text-[10px] uppercase tracking-[0.06em] text-ink-3">
              Type &amp; color
            </div>
            <SelectControl
              label="Display font"
              value={tweaks.font}
              options={FONT_OPTIONS}
              onChange={(v) => setTweak("font", v)}
            />
            <ColorChips
              label="Accent"
              value={tweaks.accent}
              options={ACCENT_OPTIONS}
              onChange={(v) => setTweak("accent", v)}
            />
            <div className="font-mono text-[10px] uppercase tracking-[0.06em] text-ink-3">
              Density
            </div>
            <Segmented
              label="Spacing"
              value={tweaks.density}
              options={["comfortable", "compact"]}
              onChange={(v) => setTweak("density", v as typeof tweaks.density)}
            />
          </div>
        </div>
      )}
    </>
  );
}
