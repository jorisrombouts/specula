import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LanguageEditor } from "@/components/candidate/language-editor";

afterEach(cleanup);
const rows = [{ language: "English", level: "Native" as const }];

describe("LanguageEditor", () => {
  it("adds a row with the default level", () => {
    const onChange = vi.fn();
    render(<LanguageEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add language"));
    expect(onChange).toHaveBeenCalledWith([
      { language: "English", level: "Native" },
      { language: "", level: "Native" },
    ]);
  });

  it("edits a row's language", () => {
    const onChange = vi.fn();
    render(<LanguageEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("language 1"), {
      target: { value: "Dutch" },
    });
    expect(onChange).toHaveBeenCalledWith([
      { language: "Dutch", level: "Native" },
    ]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<LanguageEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove language 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
