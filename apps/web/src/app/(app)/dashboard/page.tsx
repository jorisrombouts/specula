import { DashboardView } from "@/components/dashboard/dashboard-view";
import { getDashboard } from "@/lib/api/dashboard";

export default async function DashboardPage() {
  return <DashboardView summary={await getDashboard()} />;
}
