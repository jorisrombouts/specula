import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ViewShell } from "@/components/view-shell";

afterEach(cleanup);

describe("ViewShell", () => {
  it("renders its screen-label, title, and sub", () => {
    const { container } = render(
      <ViewShell label="jobs" title="Jobs" sub="The pool of roles." />,
    );
    expect(
      container.querySelector('[data-screen-label="jobs"]'),
    ).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
    expect(screen.getByText("The pool of roles.")).toBeInTheDocument();
  });
});
