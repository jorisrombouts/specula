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
  it("renders the profile field values", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByDisplayValue(c.title)).toBeInTheDocument();
    expect(screen.getByDisplayValue(c.location)).toBeInTheDocument();
  });

  it("renders the skills-gap panel with a gap item", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByText("Skills gap")).toBeInTheDocument();
    expect(screen.getByText(gap[0].skill)).toBeInTheDocument();
  });

  it("gates Save on dirty state", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const save = screen.getByText("Save profile");
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByDisplayValue(c.title), {
      target: { value: "Staff ML Engineer" },
    });
    expect(save).not.toBeDisabled();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("adds a demanded skill from the skills-gap panel and drops the gap row", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const target = gap[0].skill;
    fireEvent.click(screen.getByLabelText(`add ${target} to skills`));
    expect(screen.getByLabelText(`remove ${target}`)).toBeInTheDocument();
    expect(screen.queryByLabelText(`add ${target} to skills`)).toBeNull();
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
    expect(Array.isArray(body.workMode)).toBe(true);
    fetchMock.mockRestore();
  });
});
