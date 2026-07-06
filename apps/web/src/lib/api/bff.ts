// PLACEHOLDER — replaced by the M2 Frontend-wiring lane.
//
// That lane builds the real server-side helper that mints a service JWT from the
// signed-in session and calls FastAPI. Until it lands, this throws so callers
// fall back (reads) or surface the gap (writes) instead of silently returning
// wrong data. Do NOT build the minter here — see
// docs/superpowers/specs/m2-fanout-playbook.md.
export async function bffFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  throw new Error(
    `bffFetch(${init?.method ?? "GET"} ${path}) not wired yet — pending the M2 Frontend-wiring lane`,
  );
}
