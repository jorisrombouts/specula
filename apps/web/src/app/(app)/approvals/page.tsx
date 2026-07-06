import { ApprovalsView } from "@/components/approvals/approvals-view";
import { getApprovals } from "@/lib/api/approvals";

export default async function ApprovalsPage() {
  return <ApprovalsView approvals={await getApprovals()} />;
}
