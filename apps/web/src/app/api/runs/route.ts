import { NextResponse } from "next/server";
import { bffFetchRaw } from "@/lib/api/bff";

// Triggers a new pipeline run. Forwards FastAPI's real status + body so the client can tell a
// rate-limit (429 with retryAfterS) from a genuine failure, instead of collapsing every error
// into an opaque 500. A total failure to reach FastAPI surfaces as a 502.
export async function POST(): Promise<NextResponse> {
  try {
    const res = await bffFetchRaw("/runs", { method: "POST" });
    const body = res.status === 204 ? null : await res.json().catch(() => null);
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ error: "unreachable" }, { status: 502 });
  }
}
