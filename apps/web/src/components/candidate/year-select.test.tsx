import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { YearSelect } from "@/components/candidate/year-select";

afterEach(cleanup);

describe("YearSelect", () => {
  it("shows the current value as selected", () => {
    render(<YearSelect value={2019} onChange={() => {}} ariaLabel="Year" />);
    expect((screen.getByLabelText("Year") as HTMLSelectElement).value).toBe(
      "2019",
    );
  });

  it("emits a number when a year is chosen", () => {
    const onChange = vi.fn();
    render(<YearSelect value={null} onChange={onChange} ariaLabel="Year" />);
    fireEvent.change(screen.getByLabelText("Year"), {
      target: { value: "2020" },
    });
    expect(onChange).toHaveBeenCalledWith(2020);
  });

  it("emits null when the blank option is chosen", () => {
    const onChange = vi.fn();
    render(
      <YearSelect
        value={2020}
        onChange={onChange}
        ariaLabel="End year"
        presentLabel="Present"
      />,
    );
    expect(screen.getByRole("option", { name: "Present" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("End year"), {
      target: { value: "" },
    });
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
