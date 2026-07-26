import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const { TargetingView } = await import("@/components/targeting/targeting-view");
const { getTargeting } = await import("@/lib/api/targeting");

afterEach(() => {
  cleanup();
  refresh.mockReset();
});
const t = await getTargeting();

describe("TargetingView", () => {
  it("renders tag fields, seniority toggles, preferences, and the invariant banner", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getByText(t.roleTitles[0])).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t.seniority[0] }),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue(t.preferences)).toBeInTheDocument();
    expect(screen.getByText(/never a rule or signal/)).toBeInTheDocument();
  });

  it("has three tag editors (role titles, must-haves, avoid)", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getAllByText("+ add")).toHaveLength(3);
  });

  it("gates Save on dirty state and toggles seniority", () => {
    render(<TargetingView targeting={t} />);
    const save = screen.getByText("Save targeting");
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Principal" })); // not in seed seniority
    expect(save).not.toBeDisabled();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("adds a role title via the suggestions input (free-add)", () => {
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getAllByText("+ add")[0]); // first TagEditor = role titles
    const input = document.activeElement as HTMLInputElement;
    expect(input).toHaveAttribute("list"); // suggestions datalist wired
    fireEvent.change(input, { target: { value: "LLM Engineer" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByText("LLM Engineer")).toBeInTheDocument();
  });

  it("Save targeting PUTs the edited fields through the BFF route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getByRole("button", { name: "Principal" }));
    fireEvent.click(screen.getByText("Save targeting"));
    await screen.findByText("Saved.");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/targeting",
      expect.objectContaining({ method: "PUT" }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init!.body as string);
    expect(body.seniority).toContain("Principal");
    fetchMock.mockRestore();
  });

  // Same client-cache invalidation the candidate profile needs: Next reuses this page's
  // rendered payload on browser back/forward, so without a refresh a save→leave→Back
  // round-trip re-renders the stale pre-save targeting.
  it("clears the client cache after save so browser Back isn't stale", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getByRole("button", { name: "Principal" }));
    fireEvent.click(screen.getByText("Save targeting"));
    await screen.findByText("Saved.");

    expect(refresh).toHaveBeenCalled();
    fetchMock.mockRestore();
  });
});
