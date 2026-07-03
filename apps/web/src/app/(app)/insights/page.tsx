import { InsightsView } from "@/components/insights/insights-view";
import { getInsights } from "@/lib/api/insights";

export default function InsightsPage() {
  return <InsightsView insights={getInsights()} />;
}
