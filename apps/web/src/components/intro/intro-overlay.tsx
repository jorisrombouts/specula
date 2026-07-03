"use client";

import { useEffect, useState } from "react";
import { useCountUp } from "@/lib/use-count-up";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

export function IntroOverlay({
  roles,
  isNew,
  onDone,
}: {
  roles: number;
  isNew: number;
  onDone: () => void;
}) {
  const reduce = usePrefersReducedMotion();
  const [leaving, setLeaving] = useState(false);
  const rolesShown = useCountUp(roles, !reduce, 1500);

  useEffect(() => {
    const finish = () => {
      setLeaving((was) => {
        if (!was) setTimeout(onDone, reduce ? 0 : 640);
        return true;
      });
    };
    const t = setTimeout(finish, reduce ? 250 : 2000);
    const onKey = () => finish();
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dismiss = () =>
    setLeaving((was) => {
      if (!was) setTimeout(onDone, reduce ? 0 : 640);
      return true;
    });

  return (
    <div
      onClick={dismiss}
      className={`fixed inset-0 z-[200] flex cursor-pointer flex-col items-center justify-center overflow-hidden bg-paper ${leaving ? "[animation:introLeave_0.64s_cubic-bezier(0.6,0,0.25,1)_forwards]" : ""}`}
    >
      <div className="relative text-center">
        <div className="intro-anim font-display text-[86px] font-semibold leading-[0.9] tracking-[0.02em] text-ink opacity-0 [animation:introMark_1s_cubic-bezier(0.2,0.7,0.2,1)_0.15s_forwards]">
          Specula
        </div>
        <div className="intro-anim mx-auto mt-[24px] h-[2px] w-0 bg-ink [animation:introRule_0.85s_cubic-bezier(0.6,0,0.15,1)_0.6s_forwards]" />
        <div className="intro-anim mt-[18px] font-mono text-[13px] uppercase tracking-[0.26em] text-ink-2 opacity-0 [animation:introFade_0.7s_ease_0.95s_forwards]">
          personal role ledger
        </div>
        <div className="mx-auto mt-[34px] flex w-[316px] flex-col gap-[10px]">
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className="intro-anim h-px origin-left scale-x-0 bg-rule-2 [animation:introLine_0.55s_cubic-bezier(0.4,0,0.2,1)_forwards]"
              style={{ animationDelay: `${0.62 + i * 0.1}s` }}
            />
          ))}
        </div>
        <div className="intro-anim mt-[28px] font-mono text-[12px] text-ink-2 opacity-0 [animation:introFade_0.7s_ease_1.2s_forwards]">
          synced ·{" "}
          <b className="font-semibold text-ink">
            {reduce ? roles : rolesShown}
          </b>{" "}
          roles tracked · <b className="font-semibold text-ink">{isNew}</b> new
          this week
        </div>
      </div>
      <div className="intro-anim absolute bottom-[40px] left-0 right-0 text-center font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3 opacity-0 [animation:introFade_0.7s_ease_1.6s_forwards]">
        click anywhere to enter
      </div>
    </div>
  );
}
