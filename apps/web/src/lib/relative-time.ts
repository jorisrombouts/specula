const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

// Coarse, bucketed relative time ("just now" / "3m ago" / "2h ago" / "5d ago"),
// matching the "Nd ago" style used across the app. `now` is passed in (read once
// at mount) so a pinned clock stays deterministic for the visual/e2e harness.
export function relative(finishedAt: string, now: number): string {
  const diff = Math.max(0, now - new Date(finishedAt).getTime());
  if (diff < MINUTE_MS) return "just now";
  if (diff < HOUR_MS) return `${Math.floor(diff / MINUTE_MS)}m ago`;
  if (diff < DAY_MS) return `${Math.floor(diff / HOUR_MS)}h ago`;
  return `${Math.floor(diff / DAY_MS)}d ago`;
}
