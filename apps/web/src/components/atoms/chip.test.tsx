import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { Chip } from "@/components/atoms/chip";

afterEach(cleanup);

describe("Chip", () => {
  it("default uses ink-2 text + rule border", () => {
    render(<Chip>x</Chip>);
    const el = screen.getByText("x");
    expect(el.className).toContain("text-ink-2");
    expect(el.className).toContain("border-rule");
    expect(el.className).not.toContain("text-ink ");
  });

  it("strong uses ink text + rule-2 border", () => {
    render(<Chip strong>y</Chip>);
    const el = screen.getByText("y");
    expect(el.className).toContain("text-ink");
    expect(el.className).toContain("border-rule-2");
  });

  it("mono and strong compose", () => {
    render(
      <Chip mono strong>
        z
      </Chip>,
    );
    const el = screen.getByText("z");
    expect(el.className).toContain("font-mono");
    expect(el.className).toContain("border-rule-2");
  });
});
