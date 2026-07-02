import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { TagEditor } from "@/components/atoms/tag-editor";

afterEach(cleanup);

describe("TagEditor", () => {
  it("renders the current values as chips", () => {
    render(<TagEditor values={["Python", "RAG"]} onChange={() => {}} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("RAG")).toBeInTheDocument();
  });
  it("removes a value on clicking its ×", () => {
    const onChange = vi.fn();
    render(<TagEditor values={["Python", "RAG"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /remove Python/i }));
    expect(onChange).toHaveBeenCalledWith(["RAG"]);
  });
  it("adds a value via the + add input on Enter", () => {
    const onChange = vi.fn();
    render(<TagEditor values={["Python"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "vLLM" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["Python", "vLLM"]);
  });
});
