import { TargetingView } from "@/components/targeting/targeting-view";
import { getTargeting } from "@/lib/api/targeting";

export default function TargetingPage() {
  return <TargetingView targeting={getTargeting()} />;
}
