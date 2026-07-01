import { NextResponse } from "next/server";
import type { JobSort, JobsResponse } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import {
  filterByLens,
  scoreForLens,
  deriveLensSummaries,
  sortJobs,
} from "@/lib/seed/logic";

export function GET(request: Request): NextResponse<JobsResponse> {
  const url = new URL(request.url);
  const lens = url.searchParams.get("lens") ?? "all";
  const sortParam = url.searchParams.get("sort");
  const sort: JobSort =
    sortParam === "deadline" || sortParam === "new" ? sortParam : "match";

  const scored = filterByLens(jobs, lens).map((job) => {
    const s = scoreForLens(job, lens);
    return { ...job, match: s.match, factors: s.factors, redFlag: s.redFlag };
  });

  return NextResponse.json({
    jobs: sortJobs(scored, sort),
    lenses: deriveLensSummaries(lenses, jobs),
    sort,
  });
}
