import { NextResponse } from "next/server";
import type { ApprovalDecision } from "@/lib/api/approvals";

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

  // Frontend-wiring lane: forward to FastAPI `POST /approvals/{id}/decision`
  // via the shared service-JWT `bffFetch`. Until that exists, acknowledge so the
  // queue UI is fully wired client-side.
  return NextResponse.json({ ok: true, id, decision: body.decision });
}
