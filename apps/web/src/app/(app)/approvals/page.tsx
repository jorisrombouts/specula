import { ApprovalsView } from "@/components/approvals/approvals-view";
import { getApprovals } from "@/lib/api/approvals";
import { getLatestRun } from "@/lib/api/runs";

export default async function ApprovalsPage() {
  const [approvals, latestRun] = await Promise.all([
    getApprovals(),
    getLatestRun(),
  ]);
  return <ApprovalsView approvals={approvals} latestRun={latestRun} />;
}
