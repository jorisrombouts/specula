import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { CompaniesView } from "@/components/companies/companies-view";
import type { CompanyRow } from "@/lib/api/companies";
import { companies } from "@/lib/seed/data";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

afterEach(cleanup);
afterEach(() => vi.restoreAllMocks());

describe("CompaniesView", () => {
  it("renders DERIVED tracked count (10) and open-roles sum (67)", () => {
    const { container } = render(
      <CompaniesView companies={companies} latestRun={null} />,
    );
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("10");
    expect(header).toHaveTextContent("tracked");
    expect(header).toHaveTextContent("67");
    expect(header).toHaveTextContent("open roles");
  });

  it("renders one table row per company", () => {
    const { container } = render(
      <CompaniesView companies={companies} latestRun={null} />,
    );
    expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  });

  it("flags HQ confidence < 80 with warn styling + ⚐, and not for >= 80", () => {
    render(<CompaniesView companies={companies} latestRun={null} />);
    // Sereact = 64 (<80): warn conf cell with ⚐
    expect(screen.getByText(/64% ⚐/)).toBeInTheDocument();
    // Mistral AI = 98 (>=80): plain, no ⚐
    expect(screen.getByText("98%")).toBeInTheDocument();
  });

  it("filters rows by name or HQ (case-insensitive) and updates the N of M count", () => {
    const { container } = render(
      <CompaniesView companies={companies} latestRun={null} />,
    );
    const input = screen.getByPlaceholderText(/Filter by name or HQ/);
    fireEvent.change(input, { target: { value: "france" } });
    // France HQ: Mistral AI, Qonto, Pigment = 3
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(screen.getByText("3 of 10")).toBeInTheDocument();
  });

  it("renders the comp-est chip and a Remove action per row", () => {
    render(<CompaniesView companies={companies} latestRun={null} />);
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(10);
    expect(screen.getAllByText("€€€").length).toBeGreaterThan(0);
  });

  it("removes a row via /opt-out and drops it from the table", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));
    const rows: CompanyRow[] = [
      { ...companies[0], id: "co-1" },
      { ...companies[1], id: "co-2" },
    ];
    const { container } = render(
      <CompaniesView companies={rows} latestRun={null} />,
    );
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);

    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);

    // optimistic drop
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/companies/co-1/opt-out");
    expect(init?.method).toBe("POST");
  });
});
