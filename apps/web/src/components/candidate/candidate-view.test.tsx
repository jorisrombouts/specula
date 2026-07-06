import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CandidateView } from "@/components/candidate/candidate-view";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getCandidate } = await import("@/lib/api/candidate");
const { getSkillsGap } = await import("@/lib/api/skills-gap");

afterEach(cleanup);
const c = await getCandidate();
const gap = await getSkillsGap();

describe("CandidateView", () => {
  it("renders the profile field values (name/initials aren't sourced from the API)", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(c.initials).toBe(""); // not stored server-side; sourced from the session elsewhere
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

  it("Save profile PUTs the edited fields through the BFF route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<CandidateView candidate={c} skillsGap={gap} />);

    fireEvent.change(screen.getByDisplayValue(c.title), {
      target: { value: "Staff ML Engineer" },
    });
    fireEvent.click(screen.getByText("Save profile"));
    await screen.findByText("Saved.");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/candidate",
      expect.objectContaining({ method: "PUT" }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init!.body as string);
    expect(body.headline).toBe("Staff ML Engineer");
    fetchMock.mockRestore();
  });
});
