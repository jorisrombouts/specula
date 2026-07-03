import type { Insights } from "@specula/shared-types";
import { insights } from "@/lib/seed/data";

export function getInsights(): Insights {
  return insights;
}
