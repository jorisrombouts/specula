import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  fireEvent,
  cleanup,
  within,
  screen,
  waitFor,
} from "@testing-library/react";
import { ProfilesView } from "@/components/profiles/profiles-view";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getLenses } = await import("@/lib/api/lenses");

afterEach(cleanup);
const lenses = await getLenses();

function mockFetchOk(body: unknown = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
}

describe("ProfilesView", () => {
  it("shows DERIVED active/total (4 active / 5 total) and 4 cards (excludes the default)", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("4");
    expect(header).toHaveTextContent("active");
    expect(header).toHaveTextContent("5");
    expect(header).toHaveTextContent("total");
    expect(container.querySelectorAll("[data-lens]")).toHaveLength(4);
    expect(container.querySelector('[data-lens="all"]')).toBeNull();
  });

  it("renders a lens card's DERIVED count badge + scope", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const remote = lenses.find((l) => l.id === "remote")!;
    const card = container.querySelector('[data-lens="remote"]') as HTMLElement;
    expect(
      within(card).getByText(`${remote.count} roles · ${remote.isNew} new`),
    ).toBeInTheDocument();
    expect(card).toHaveTextContent("EU"); // scope "EU" shown as "Region · EU"
  });

  it("+ New profile adds an editable card", () => {
    render(<ProfilesView lenses={lenses} />);
    expect(screen.queryByText("Save profile")).toBeNull();
    fireEvent.click(screen.getByText("+ New profile"));
    expect(screen.getByText("Save profile")).toBeInTheDocument();
  });

  it("toggling a lens flips it and PATCHes active", async () => {
    const fetchMock = mockFetchOk({});
    const { container } = render(<ProfilesView lenses={lenses} />);
    const berlin = container.querySelector(
      '[data-lens="berlin"]',
    ) as HTMLElement;
    expect(berlin.getAttribute("data-active")).toBe("false");
    fireEvent.click(within(berlin).getByRole("switch"));
    expect(
      container
        .querySelector('[data-lens="berlin"]')!
        .getAttribute("data-active"),
    ).toBe("true"); // optimistic
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/lenses/berlin"),
      expect.objectContaining({ method: "PATCH" }),
    );
    fetchMock.mockRestore();
  });

  it("editing a card and saving PATCHes with the mapped payload", async () => {
    const fetchMock = mockFetchOk(lenses.find((l) => l.id === "spain"));
    const { container } = render(<ProfilesView lenses={lenses} />);
    const spain = container.querySelector('[data-lens="spain"]') as HTMLElement;
    fireEvent.click(within(spain).getByText("Edit"));
    fireEvent.change(screen.getByLabelText("focus"), {
      target: { value: "Madrid only" },
    });
    fireEvent.click(screen.getByText("Save profile"));
    // back to read-only after save — scoped to spain's own card: every other
    // (non-editing) row also renders its own "Edit" button, so an unscoped
    // screen.findByText("Edit") would always see multiple matches.
    await waitFor(() => {
      expect(container.querySelector('[data-lens="spain"]')).not.toBeNull();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/lenses/spain"),
      expect.objectContaining({ method: "PATCH" }),
    );
    const body = JSON.parse(
      (fetchMock.mock.calls[0][1] as RequestInit).body as string,
    );
    expect(body.focus).toBe("Madrid only");
    expect(body.scope).toBe("ES");
    fetchMock.mockRestore();
  });
});
