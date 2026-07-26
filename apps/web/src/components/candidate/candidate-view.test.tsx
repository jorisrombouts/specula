import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const { CandidateView } = await import("@/components/candidate/candidate-view");
const { getCandidate } = await import("@/lib/api/candidate");
const { getSkillsGap } = await import("@/lib/api/skills-gap");

afterEach(() => {
  cleanup();
  refresh.mockReset();
});
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

  // The gap row vanishing reads as "committed", so the click must actually commit —
  // staging it behind a separate Save button is how the skill silently disappeared.
  it("persists a skills-gap add immediately, without pressing Save", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const target = gap[0].skill;

    fireEvent.click(screen.getByLabelText(`add ${target} to skills`));
    await screen.findByText("Saved.");

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init!.body as string);
    expect(body.skills).toContain(target);
    expect(screen.queryByText("Unsaved changes")).toBeNull();
    expect(refresh).toHaveBeenCalled();
    fetchMock.mockRestore();
  });

  // If the write fails, the gap row must come back — otherwise the UI claims a skill
  // was added that isn't stored anywhere, which is the original bug in a new costume.
  it("restores the gap row when the immediate save fails", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("nope", { status: 500 }));
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const target = gap[0].skill;

    fireEvent.click(screen.getByLabelText(`add ${target} to skills`));
    expect(
      await screen.findByLabelText(`add ${target} to skills`),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(`remove ${target}`)).toBeNull();
    fetchMock.mockRestore();
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

  // Next's client cache reuses a page's RSC payload on browser back/forward navigation
  // (it is NOT refetched like a <Link> nav). Without invalidating it after a save, going
  // to another page and pressing Back re-renders the PRE-save server payload — the just-
  // saved edit silently vanishes even though it is safely in the DB.
  it("clears the client cache after save so browser Back isn't stale", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<CandidateView candidate={c} skillsGap={gap} />);

    fireEvent.change(screen.getByDisplayValue(c.title), {
      target: { value: "Staff ML Engineer" },
    });
    fireEvent.click(screen.getByText("Save profile"));
    await screen.findByText("Saved.");

    expect(refresh).toHaveBeenCalled();
    fetchMock.mockRestore();
  });
});
