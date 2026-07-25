import { CompaniesView } from "@/components/companies/companies-view";
import { getCompanies } from "@/lib/api/companies";
import { getLatestRun } from "@/lib/api/runs";

export default async function CompaniesPage() {
  const [companies, latestRun] = await Promise.all([
    getCompanies(),
    getLatestRun(),
  ]);
  return <CompaniesView companies={companies} latestRun={latestRun} />;
}
