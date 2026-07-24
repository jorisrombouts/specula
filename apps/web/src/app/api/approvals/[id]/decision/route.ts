import { NextResponse } from "next/server";
import type { ApprovalDecision } from "@/lib/api/approvals";
import { bffFetchRaw } from "@/lib/api/bff";

const DECISIONS = new Set<ApprovalDecision>(["approve", "reject", "snooze"]);

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const body = (await request.json()) as { decision?: string };
  if (!body.decision || !DECISIONS.has(body.decision as ApprovalDecision)) {
    return NextResponse.json({ error: "invalid decision" }, { status: 400 });
  }

  // Forward FastAPI's real status + body so a rate-limited approve (429 with retryAfterS)
  // surfaces to the user instead of collapsing to an opaque 500.
  const res = await bffFetchRaw(`/approvals/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision: body.decision }),
  });
  const payload =
    res.status === 204 ? null : await res.json().catch(() => null);
  return NextResponse.json(payload, { status: res.status });
}
