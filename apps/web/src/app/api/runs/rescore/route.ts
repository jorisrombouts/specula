import { NextResponse } from "next/server";
import { bffFetchRaw } from "@/lib/api/bff";

// Re-score all existing jobs against the current profile. Forwards FastAPI's real status + body
// so a rate-limited re-score (429 with retryAfterS) surfaces to the user. A total failure to
// reach FastAPI surfaces as a 502.
export async function POST(): Promise<NextResponse> {
  try {
    const res = await bffFetchRaw("/runs/rescore", { method: "POST" });
    const body = res.status === 204 ? null : await res.json().catch(() => null);
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ error: "unreachable" }, { status: 502 });
  }
}
