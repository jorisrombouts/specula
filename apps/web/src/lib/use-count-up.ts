"use client";

import { useEffect, useState } from "react";

export function useCountUp(target: number, run: boolean, dur = 900): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setV(0);
      return;
    }
    let raf = 0;
    let start = 0;
    const step = (t: number) => {
      if (!start) start = t;
      const p = Math.min((t - start) / dur, 1);
      const e = 1 - Math.pow(1 - p, 3);
      setV(Math.round(target * e));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, run, dur]);
  return v;
}
