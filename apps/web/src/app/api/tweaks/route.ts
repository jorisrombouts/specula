import { NextResponse } from "next/server";
import { getTweaks, putTweaks } from "@/lib/api/tweaks";
import type { Tweaks } from "@/lib/tweaks-init";

export function GET(): NextResponse {
  return NextResponse.json(getTweaks());
}

export async function PUT(req: Request): Promise<NextResponse> {
  const body = (await req.json()) as Tweaks;
  return NextResponse.json(putTweaks(body));
}
