import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CandidateView } from "@/components/candidate/candidate-view";
import { getCandidate } from "@/lib/api/candidate";
import { getSkillsGap } from "@/lib/api/skills-gap";

afterEach(cleanup);
const c = getCandidate();
const gap = getSkillsGap();

describe("CandidateView", () => {
  it("renders the seed avatar initials + field values", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByText(c.initials)).toBeInTheDocument(); // "JV" from seed, not session
    expect(screen.getByDisplayValue(c.title)).toBeInTheDocument();
    expect(screen.getByDisplayValue(c.location)).toBeInTheDocument();
  });

  it("renders the skills-gap panel with a gap item", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByText("Skills gap")).toBeInTheDocument();
    expect(screen.getByText(gap[0].skill)).toBeInTheDocument();
    expect(screen.getByText(`${gap[0].roles}×`)).toBeInTheDocument();
  });

  it("removes and adds a skill tag locally (wiring)", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const first = c.skills[0];
    // remove the first skill chip via its × (aria-label from the TagEditor atom)
    fireEvent.click(screen.getByLabelText(`remove ${first}`));
    expect(screen.queryByLabelText(`remove ${first}`)).toBeNull();
    // add a new skill: the single "+ add" is the Skills TagEditor's
    fireEvent.click(screen.getByText("+ add"));
    const input = document.activeElement as HTMLInputElement; // autofocused add input
    fireEvent.change(input, { target: { value: "GraphQL" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByText("GraphQL")).toBeInTheDocument();
  });
});
