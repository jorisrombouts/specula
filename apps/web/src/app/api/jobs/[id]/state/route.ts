import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

// The drawer's status / note / feedback / dismiss controls PATCH here, which
// forwards to FastAPI PATCH /jobs/{id}/state.
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const patch = await request.json();
  const state = await bffFetch(`/jobs/${id}/state`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return NextResponse.json(state);
}
