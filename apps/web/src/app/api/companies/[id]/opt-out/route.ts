import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

// "Remove" a company: proxy to FastAPI POST /companies/{id}/opt-out (204). The
// browser never calls FastAPI directly — only the Next server does.
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  await bffFetch(`/companies/${id}/opt-out`, { method: "POST" });
  return new NextResponse(null, { status: 204 });
}
