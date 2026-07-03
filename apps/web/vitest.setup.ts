import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement matchMedia at all (unlike requestAnimationFrame,
// which Vitest's jsdom environment provides via pretendToBeVisual). Stub a
// "no preference" default so any component reading it can render in tests;
// individual tests can still vi.stubGlobal("matchMedia", ...) to override.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }) as unknown as MediaQueryList;
}

// jsdom doesn't implement the Web Animations API (Element.animate). Stub a
// no-op so components using WAAPI (morph/FLIP/drawer transitions) can run in
// tests without throwing; they fall back to their own setTimeout completions.
if (typeof Element !== "undefined" && !Element.prototype.animate) {
  Element.prototype.animate = (() =>
    ({
      onfinish: null,
    }) as unknown as Animation) as typeof Element.prototype.animate;
}
