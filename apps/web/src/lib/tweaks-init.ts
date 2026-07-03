export type Mstyle = "bars" | "figure" | "ring";
export type Layout = "rows" | "cards";
export type Density = "comfortable" | "compact";
export interface Tweaks {
  mstyle: Mstyle;
  layout: Layout;
  density: Density;
  accent: string;
  font: string;
}

export const TWEAK_DEFAULTS: Tweaks = {
  mstyle: "bars",
  layout: "rows",
  density: "comfortable",
  accent: "#2E7D4F",
  font: "Spectral",
};

export const ACCENT_OPTIONS = ["#2E7D4F", "#2D5BBF", "#9A7A18", "#7A4FB0"];
export const FONT_OPTIONS = ["Spectral", "Newsreader", "Source Serif 4"];
export const STORAGE_KEY = "specula_tweaks";

const FONT_VARS: Record<string, string> = {
  Spectral: "--font-spectral",
  Newsreader: "--font-newsreader",
  "Source Serif 4": "--font-source-serif",
};

// The single source of the global-tweak → CSS mapping. Shared by the provider
// effect and (mirrored as a string) by INIT_SCRIPT.
export function applyTweaks(
  root: HTMLElement,
  t: Pick<Tweaks, "accent" | "font" | "density">,
): void {
  root.style.setProperty("--accent", t.accent);
  root.style.setProperty(
    "--accent-bg",
    `color-mix(in srgb, ${t.accent} 15%, var(--color-paper))`,
  );
  root.style.setProperty(
    "--accent-ink",
    `color-mix(in srgb, ${t.accent} 70%, #000)`,
  );
  const fontVar = FONT_VARS[t.font] ?? FONT_VARS.Spectral;
  root.style.setProperty("--font-display", `var(${fontVar}), serif`);
  root.setAttribute(
    "data-density",
    t.density === "compact" ? "compact" : "regular",
  );
}

// Blocking pre-paint script: reads localStorage and applies the same mapping so
// accent/font/density never flash. Mirrors applyTweaks (can't import pre-React).
export const INIT_SCRIPT = `(function(){try{
var t=JSON.parse(localStorage.getItem(${JSON.stringify(STORAGE_KEY)})||"{}");
var r=document.documentElement;
var a=t.accent||${JSON.stringify(TWEAK_DEFAULTS.accent)};
r.style.setProperty("--accent",a);
r.style.setProperty("--accent-bg","color-mix(in srgb, "+a+" 15%, var(--color-paper))");
r.style.setProperty("--accent-ink","color-mix(in srgb, "+a+" 70%, #000)");
var fv={"Spectral":"--font-spectral","Newsreader":"--font-newsreader","Source Serif 4":"--font-source-serif"}[t.font||"Spectral"]||"--font-spectral";
r.style.setProperty("--font-display","var("+fv+"), serif");
r.setAttribute("data-density",t.density==="compact"?"compact":"regular");
}catch(e){}})();`;
