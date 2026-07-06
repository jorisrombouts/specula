import { ProfilesView } from "@/components/profiles/profiles-view";
import { getLenses } from "@/lib/api/lenses";

export default async function ProfilesPage() {
  return <ProfilesView lenses={await getLenses()} />;
}
