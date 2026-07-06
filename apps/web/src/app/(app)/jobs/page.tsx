import { JobsView } from "@/components/jobs/jobs-view";
import { getJobsPool } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";

export default async function JobsPage() {
  const [pool, lenses, candidate] = await Promise.all([
    getJobsPool(),
    getLenses(),
    getCandidate(),
  ]);
  return <JobsView pool={pool} lenses={lenses} candidate={candidate} />;
}
