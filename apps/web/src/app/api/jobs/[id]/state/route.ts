import { NextResponse } from "next/server";

// M2: the drawer's status / note / feedback / dismiss controls PATCH here. Until the
// Frontend-wiring lane lands the shared service-JWT `bffFetch`, this echoes the patch
// back so the drawer can optimistically reconcile.
// TODO(frontend-wiring): forward to FastAPI PATCH /jobs/{id}/state via bffFetch.
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  await params;
  const patch = await request.json();
  return NextResponse.json(patch);
}
