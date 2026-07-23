import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ExperienceEditor } from "@/components/candidate/experience-editor";

afterEach(cleanup);
const rows = [{ role: "ML Eng", org: "Adyen", startYear: 2019, endYear: 2022 }];

describe("ExperienceEditor", () => {
  it("adds a blank row", () => {
    const onChange = vi.fn();
    render(<ExperienceEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add role"));
    expect(onChange).toHaveBeenCalledWith([
      rows[0],
      { role: "", org: "", startYear: null, endYear: null },
    ]);
  });

  it("sets endYear to null (Present) via the end-year select", () => {
    const onChange = vi.fn();
    render(<ExperienceEditor value={rows} onChange={onChange} />);
    expect(screen.getByRole("option", { name: "Present" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("end year 1"), {
      target: { value: "" },
    });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], endYear: null }]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<ExperienceEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove role 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
