import { SettingsView } from "@/components/settings/settings-view";
import { getDiscoverySettings } from "@/lib/api/discovery-settings";

export default async function SettingsPage() {
  const { maxSearches } = await getDiscoverySettings();
  return <SettingsView initialMaxSearches={maxSearches} />;
}
