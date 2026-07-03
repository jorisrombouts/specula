import { ApprovalsView } from "@/components/approvals/approvals-view";
import { getApprovals } from "@/lib/api/approvals";

export default function ApprovalsPage() {
  return <ApprovalsView approvals={getApprovals()} />;
}
