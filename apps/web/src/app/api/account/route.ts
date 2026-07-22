import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

// Deletes the caller's account (mirrors the client-through-BFF pattern). FastAPI cascades
// the FK deletes across every per-user table.
export async function DELETE(): Promise<NextResponse> {
  await bffFetch("/account", { method: "DELETE" });
  return new NextResponse(null, { status: 204 });
}
