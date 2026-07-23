import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";

afterEach(cleanup);
const OPTS = ["A", "B", "C"] as const;

describe("ChipMultiSelect", () => {
  it("reflects selection via aria-pressed", () => {
    render(
      <ChipMultiSelect options={OPTS} value={["A"]} onChange={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "A" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "B" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("adds an option when an off chip is clicked", () => {
    const onChange = vi.fn();
    render(
      <ChipMultiSelect options={OPTS} value={["A"]} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith(["A", "B"]);
  });

  it("removes an option when an on chip is clicked", () => {
    const onChange = vi.fn();
    render(
      <ChipMultiSelect options={OPTS} value={["A", "B"]} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "A" }));
    expect(onChange).toHaveBeenCalledWith(["B"]);
  });
});
