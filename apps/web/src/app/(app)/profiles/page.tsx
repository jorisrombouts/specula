import { ProfilesView } from "@/components/profiles/profiles-view";
import { getLenses } from "@/lib/api/lenses";

export default function ProfilesPage() {
  return <ProfilesView lenses={getLenses()} />;
}
