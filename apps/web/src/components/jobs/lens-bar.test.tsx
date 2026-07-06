import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LensBar } from "@/components/jobs/lens-bar";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getLenses } = await import("@/lib/api/lenses");
const lenses = await getLenses();

afterEach(cleanup);

describe("LensBar", () => {
  it("shows DERIVED per-lens counts (all → 13 roles · 7 new, not 47/11)", () => {
    render(<LensBar lenses={lenses} active="all" onSelect={() => {}} />);
    expect(screen.getByText("13 roles · 7 new")).toBeInTheDocument();
    expect(screen.queryByText(/47 roles/)).toBeNull();
  });

  it("marks the active lens", () => {
    const { container } = render(
      <LensBar lenses={lenses} active="all" onSelect={() => {}} />,
    );
    // active cell carries bg-ink
    expect(container.querySelector("button.bg-ink")).not.toBeNull();
  });

  it("calls onSelect with the lens id on click", () => {
    const onSelect = vi.fn();
    render(<LensBar lenses={lenses} active="all" onSelect={onSelect} />);
    const remoteShort = lenses.find((l) => l.id === "remote")!.short;
    fireEvent.click(screen.getByText(remoteShort).closest("button")!);
    expect(onSelect).toHaveBeenCalledWith("remote");
  });
});
