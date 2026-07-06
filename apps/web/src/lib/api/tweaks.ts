import { type Tweaks, TWEAK_DEFAULTS } from "@/lib/tweaks-init";

// M2: BFF → FastAPI. The shared service-JWT `bffFetch` lands with the
// frontend-wiring lane; until then GET returns the defaults and PUT echoes the
// validated body. Swap both bodies for `await bffFetch("/tweaks", ...)`.
export function getTweaks(): Tweaks {
  return TWEAK_DEFAULTS;
}

export function putTweaks(tweaks: Tweaks): Tweaks {
  return tweaks;
}
