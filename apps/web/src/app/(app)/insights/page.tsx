import { InsightsView } from "@/components/insights/insights-view";
import { getInsights } from "@/lib/api/insights";

export default async function InsightsPage() {
  return <InsightsView insights={await getInsights()} />;
}
