import { CandidateView } from "@/components/candidate/candidate-view";
import { getCandidate } from "@/lib/api/candidate";
import { getSkillsGap } from "@/lib/api/skills-gap";

export default function CandidatePage() {
  return (
    <CandidateView candidate={getCandidate()} skillsGap={getSkillsGap()} />
  );
}
