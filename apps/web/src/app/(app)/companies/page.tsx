import { CompaniesView } from "@/components/companies/companies-view";
import { getCompanies } from "@/lib/api/companies";

export default function CompaniesPage() {
  return <CompaniesView companies={getCompanies()} />;
}
