"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  type Tweaks,
  TWEAK_DEFAULTS,
  STORAGE_KEY,
  applyTweaks,
} from "@/lib/tweaks-init";

type Ctx = {
  tweaks: Tweaks;
  setTweak: <K extends keyof Tweaks>(key: K, value: Tweaks[K]) => void;
};
const TweaksContext = createContext<Ctx | null>(null);

export function TweaksProvider({ children }: { children: React.ReactNode }) {
  const [tweaks, setTweaks] = useState<Tweaks>(TWEAK_DEFAULTS);

  // `first` skips the persist effect's initial run; `dirty` marks a user edit so
  // it's PUT to the server; `edited` latches once the user has interacted so a
  // slow initial GET can't clobber an edit made while it was in flight.
  const first = useRef(true);
  const dirty = useRef(false);
  const edited = useRef(false);

  // Reconcile after mount. The localStorage cache (also read pre-paint by the
  // FOUC init script) gives an instant value; the server is the source of truth,
  // so its response wins and refreshes the cache. Neither is a user "change", so
  // the persist effect below skips the PUT for both (see `dirty`).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTweaks((t) => ({ ...t, ...(JSON.parse(raw) as Partial<Tweaks>) }));
      }
    } catch {
      /* ignore */
    }

    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/tweaks");
        if (!res.ok) return;
        const server = (await res.json()) as Partial<Tweaks>;
        if (!cancelled && !edited.current) {
          setTweaks((t) => ({ ...t, ...server }));
        }
      } catch {
        /* offline / not signed in: keep the cached value */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Apply + persist on change. Skip the FIRST run: the init script already
  // applied the pre-paint values, so applying defaults here would clobber them.
  // `dirty` tells a user edit (→ PUT to the server) apart from a mount
  // reconcile (localStorage/server → cache + CSS only, no write-back).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    applyTweaks(document.documentElement, tweaks);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tweaks));
    } catch {
      /* ignore */
    }
    if (dirty.current) {
      dirty.current = false;
      void (async () => {
        try {
          await fetch("/api/tweaks", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(tweaks),
          });
        } catch {
          /* keep the local value; a later edit retries */
        }
      })();
    }
  }, [tweaks]);

  const setTweak = useCallback(
    <K extends keyof Tweaks>(key: K, value: Tweaks[K]) => {
      dirty.current = true;
      edited.current = true;
      setTweaks((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  return (
    <TweaksContext.Provider value={{ tweaks, setTweak }}>
      {children}
    </TweaksContext.Provider>
  );
}

export function useTweaks(): Ctx {
  const ctx = useContext(TweaksContext);
  if (!ctx) throw new Error("useTweaks must be used within a TweaksProvider");
  return ctx;
}
