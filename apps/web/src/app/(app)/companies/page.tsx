import { CompaniesView } from "@/components/companies/companies-view";
import { getCompanies } from "@/lib/api/companies";

export default async function CompaniesPage() {
  return <CompaniesView companies={await getCompanies()} />;
}
