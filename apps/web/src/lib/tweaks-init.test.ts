import { describe, it, expect } from "vitest";
import {
  applyTweaks,
  INIT_SCRIPT,
  TWEAK_DEFAULTS,
  STORAGE_KEY,
} from "@/lib/tweaks-init";

describe("applyTweaks", () => {
  it("sets accent (+ color-mix derivatives), font var, and density attr", () => {
    const root = document.createElement("html");
    applyTweaks(root, {
      accent: "#2D5BBF",
      font: "Newsreader",
      density: "compact",
    });
    expect(root.style.getPropertyValue("--accent")).toBe("#2D5BBF");
    expect(root.style.getPropertyValue("--accent-bg")).toBe(
      "color-mix(in srgb, #2D5BBF 15%, var(--color-paper))",
    );
    expect(root.style.getPropertyValue("--accent-ink")).toBe(
      "color-mix(in srgb, #2D5BBF 70%, #000)",
    );
    expect(root.style.getPropertyValue("--font-display")).toBe(
      "var(--font-newsreader), serif",
    );
    expect(root.getAttribute("data-density")).toBe("compact");
  });

  it("maps 'Source Serif 4' → --font-source-serif and comfortable → regular", () => {
    const root = document.createElement("html");
    applyTweaks(root, {
      accent: "#2E7D4F",
      font: "Source Serif 4",
      density: "comfortable",
    });
    expect(root.style.getPropertyValue("--font-display")).toBe(
      "var(--font-source-serif), serif",
    );
    expect(root.getAttribute("data-density")).toBe("regular");
  });

  it("INIT_SCRIPT applies persisted tweaks to documentElement before paint", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        ...TWEAK_DEFAULTS,
        accent: "#7A4FB0",
        font: "Newsreader",
      }),
    );
    // eslint-disable-next-line no-eval
    eval(INIT_SCRIPT);
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe(
      "#7A4FB0",
    );
    expect(
      document.documentElement.style.getPropertyValue("--font-display"),
    ).toBe("var(--font-newsreader), serif");
    localStorage.clear();
    document.documentElement.removeAttribute("style");
  });
});
