"use client";

import { useCountUp } from "@/lib/use-count-up";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

export function CountUp({ value, dur = 900 }: { value: number; dur?: number }) {
  const reduce = usePrefersReducedMotion();
  const shown = useCountUp(value, !reduce, dur);
  return <>{reduce ? value : shown}</>;
}
