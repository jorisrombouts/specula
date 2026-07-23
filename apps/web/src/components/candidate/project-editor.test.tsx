import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ProjectEditor } from "@/components/candidate/project-editor";

afterEach(cleanup);
const rows = [{ name: "RAG search", note: "pgvector over 2M docs" }];

describe("ProjectEditor", () => {
  it("adds a blank row", () => {
    const onChange = vi.fn();
    render(<ProjectEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add project"));
    expect(onChange).toHaveBeenCalledWith([rows[0], { name: "", note: "" }]);
  });

  it("edits the note", () => {
    const onChange = vi.fn();
    render(<ProjectEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("project note 1"), {
      target: { value: "sub-200ms p95" },
    });
    expect(onChange).toHaveBeenCalledWith([
      { ...rows[0], note: "sub-200ms p95" },
    ]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<ProjectEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove project 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
