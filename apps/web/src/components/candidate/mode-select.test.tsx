import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ModeSelect } from "@/components/candidate/mode-select";

afterEach(cleanup);

describe("ModeSelect", () => {
  it("reflects selected modes via aria-pressed", () => {
    render(<ModeSelect value={["Remote"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Remote" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Hybrid" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("adds a mode when an off toggle is clicked", () => {
    const onChange = vi.fn();
    render(<ModeSelect value={["Remote"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Hybrid" }));
    expect(onChange).toHaveBeenCalledWith(["Remote", "Hybrid"]);
  });

  it("removes a mode when an on toggle is clicked", () => {
    const onChange = vi.fn();
    render(<ModeSelect value={["Remote", "Hybrid"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Remote" }));
    expect(onChange).toHaveBeenCalledWith(["Hybrid"]);
  });
});
