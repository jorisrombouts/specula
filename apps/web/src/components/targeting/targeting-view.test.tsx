import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { TargetingView } from "@/components/targeting/targeting-view";
import { getTargeting } from "@/lib/api/targeting";

afterEach(cleanup);
const t = getTargeting();

describe("TargetingView", () => {
  it("renders tag fields, seniority chips, preferences, and the invariant banner", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getByText(t.roleTitles[0])).toBeInTheDocument();
    expect(screen.getByText(t.seniority[0])).toBeInTheDocument();
    expect(screen.getByDisplayValue(t.preferences)).toBeInTheDocument();
    expect(screen.getByText(/never a rule or signal/)).toBeInTheDocument();
  });

  it("has three tag editors (role titles, must-haves, avoid)", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getAllByText("+ add")).toHaveLength(3);
  });

  it("adds a role-title tag locally (wiring)", () => {
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getAllByText("+ add")[0]); // first TagEditor = role titles
    const input = document.activeElement as HTMLInputElement;
    fireEvent.change(input, { target: { value: "LLM Engineer" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByText("LLM Engineer")).toBeInTheDocument();
  });
});
