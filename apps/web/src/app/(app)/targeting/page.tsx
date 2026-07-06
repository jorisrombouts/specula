import { TargetingView } from "@/components/targeting/targeting-view";
import { getTargeting } from "@/lib/api/targeting";

export default async function TargetingPage() {
  return <TargetingView targeting={await getTargeting()} />;
}
