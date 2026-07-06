import { NextResponse } from "next/server";
import type { JobSort, JobsResponse } from "@specula/shared-types";
import { getJobs } from "@/lib/api/jobs";

export async function GET(
  request: Request,
): Promise<NextResponse<JobsResponse>> {
  const url = new URL(request.url);
  const lens = url.searchParams.get("lens") ?? "all";
  const sortParam = url.searchParams.get("sort");
  const sort: JobSort =
    sortParam === "deadline" || sortParam === "new" ? sortParam : "match";
  return NextResponse.json(await getJobs(lens, sort));
}
