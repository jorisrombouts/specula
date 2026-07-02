import { JobsView } from "@/components/jobs/jobs-view";
import { getJobsPool } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";

export default function JobsPage() {
  return (
    <JobsView
      pool={getJobsPool()}
      lenses={getLenses()}
      candidate={getCandidate()}
    />
  );
}
