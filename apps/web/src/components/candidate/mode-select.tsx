"use client";

import type { Mode } from "@specula/shared-types";
import { WORK_MODES } from "@specula/shared-types";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";

export function ModeSelect({
  value,
  onChange,
}: {
  value: Mode[];
  onChange: (v: Mode[]) => void;
}) {
  return (
    <ChipMultiSelect options={WORK_MODES} value={value} onChange={onChange} />
  );
}
