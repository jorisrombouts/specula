import { NextResponse } from "next/server";
import type { ApprovalDecision } from "@/lib/api/approvals";
import { bffFetch } from "@/lib/api/bff";

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

  const result = await bffFetch(`/approvals/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision: body.decision }),
  });
  return NextResponse.json(result);
}
