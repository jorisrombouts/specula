export function flipDelta(
  prev: { top: number; left: number },
  next: { top: number; left: number },
): { dx: number; dy: number } | null {
  const dx = prev.left - next.left;
  const dy = prev.top - next.top;
  if (dx === 0 && dy === 0) return null;
  return { dx, dy };
}

// Shared-element morph scale: source size over destination size, clamped so a
// wildly different pair never produces an absurd transform (prototype §9).
export function morphScale(src: number, dest: number): number {
  return Math.max(0.3, Math.min(src / dest, 1.4));
}
