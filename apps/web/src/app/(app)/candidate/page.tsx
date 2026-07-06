import { CandidateView } from "@/components/candidate/candidate-view";
import { getCandidate } from "@/lib/api/candidate";
import { getSkillsGap } from "@/lib/api/skills-gap";

export default async function CandidatePage() {
  const [candidate, skillsGap] = await Promise.all([
    getCandidate(),
    getSkillsGap(),
  ]);
  return <CandidateView candidate={candidate} skillsGap={skillsGap} />;
}
