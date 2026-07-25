import { NextResponse } from "next/server";
import { bffFetchRaw } from "@/lib/api/bff";

// Fetch a single run by id — the client polls this to follow a rescore to completion. (Static
// `/api/runs/rescore` and `/api/runs/latest` take precedence over this dynamic segment.)
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const res = await bffFetchRaw(`/runs/${encodeURIComponent(id)}`);
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  return NextResponse.json(body, { status: res.status });
}
