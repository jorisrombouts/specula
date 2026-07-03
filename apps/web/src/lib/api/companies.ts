import type { Company } from "@specula/shared-types";
import { companies } from "@/lib/seed/data";

export function getCompanies(): Company[] {
  return companies.slice();
}
