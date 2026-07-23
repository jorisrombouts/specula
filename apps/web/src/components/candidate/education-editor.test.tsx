import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { EducationEditor } from "@/components/candidate/education-editor";

afterEach(cleanup);
const rows = [{ degree: "MSc", field: "AI", institution: "UvA", year: 2019 }];

describe("EducationEditor", () => {
  it("adds a blank row", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add education"));
    expect(onChange).toHaveBeenCalledWith([
      rows[0],
      { degree: "", field: "", institution: "", year: null },
    ]);
  });

  it("edits the field name", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("field 1"), {
      target: { value: "ML" },
    });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], field: "ML" }]);
  });

  it("edits the year via the year select", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("year 1"), {
      target: { value: "2020" },
    });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], year: 2020 }]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove education 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
