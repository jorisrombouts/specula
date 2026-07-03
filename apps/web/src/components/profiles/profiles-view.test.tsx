import { describe, it, expect, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
} from "@testing-library/react";
import { ProfilesView } from "@/components/profiles/profiles-view";
import { getLenses } from "@/lib/api/lenses";

afterEach(cleanup);
const lenses = getLenses();

describe("ProfilesView", () => {
  it("shows DERIVED active/total (4 active / 5 total) and 4 cards (excludes 'all')", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("4");
    expect(header).toHaveTextContent("active");
    expect(header).toHaveTextContent("5");
    expect(header).toHaveTextContent("total");
    expect(container.querySelectorAll("[data-lens]")).toHaveLength(4);
    expect(container.querySelector('[data-lens="all"]')).toBeNull();
  });

  it("renders a lens card's DERIVED count badge + hard rules", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const remote = lenses.find((l) => l.id === "remote")!;
    const card = container.querySelector('[data-lens="remote"]') as HTMLElement;
    expect(
      within(card).getByText(`${remote.count} roles · ${remote.isNew} new`),
    ).toBeInTheDocument();
    expect(within(card).getByText(remote.scope)).toBeInTheDocument();
  });

  it("toggling a lens flips its active state locally", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const berlin = container.querySelector(
      '[data-lens="berlin"]',
    ) as HTMLElement;
    expect(berlin.getAttribute("data-active")).toBe("false"); // seed: berlin inactive
    fireEvent.click(within(berlin).getByRole("switch"));
    expect(
      container
        .querySelector('[data-lens="berlin"]')!
        .getAttribute("data-active"),
    ).toBe("true");
  });
});
