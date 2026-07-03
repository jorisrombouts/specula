"use client";

import { useEffect, useState } from "react";
import { IntroOverlay } from "@/components/intro/intro-overlay";

const KEY = "specula_intro";

export function IntroGate({ roles, isNew }: { roles: number; isNew: number }) {
  // Only decide after mount so SSR/first paint never emit the overlay (no flash
  // for returning sessions, no hydration mismatch).
  const [show, setShow] = useState(false);
  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (!sessionStorage.getItem(KEY)) setShow(true);
    } catch {
      /* sessionStorage unavailable → skip the intro */
    }
  }, []);

  if (!show) return null;
  return (
    <IntroOverlay
      roles={roles}
      isNew={isNew}
      onDone={() => {
        try {
          sessionStorage.setItem(KEY, "1");
        } catch {
          /* ignore */
        }
        setShow(false);
      }}
    />
  );
}
