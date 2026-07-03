import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CompaniesView } from "@/components/companies/companies-view";
import { getCompanies } from "@/lib/api/companies";

afterEach(cleanup);
const companies = getCompanies();

describe("CompaniesView", () => {
  it("renders DERIVED tracked count (10) and open-roles sum (67)", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("10");
    expect(header).toHaveTextContent("tracked");
    expect(header).toHaveTextContent("67");
    expect(header).toHaveTextContent("open roles");
  });

  it("renders one table row per company", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  });

  it("flags HQ confidence < 80 with warn styling + ⚐, and not for >= 80", () => {
    render(<CompaniesView companies={companies} />);
    // Sereact = 64 (<80): warn conf cell with ⚐
    expect(screen.getByText(/64% ⚐/)).toBeInTheDocument();
    // Mistral AI = 98 (>=80): plain, no ⚐
    expect(screen.getByText("98%")).toBeInTheDocument();
  });

  it("filters rows by name or HQ (case-insensitive) and updates the N of M count", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    const input = screen.getByPlaceholderText(/Filter by name or HQ/);
    fireEvent.change(input, { target: { value: "france" } });
    // France HQ: Mistral AI, Qonto, Pigment = 3
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(screen.getByText("3 of 10")).toBeInTheDocument();
  });

  it("renders the comp-est chip and an inert tracking toggle per row", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    // Toggle atom renders role="switch"; one per row
    expect(container.querySelectorAll('[role="switch"]')).toHaveLength(10);
    expect(screen.getAllByText("€€€").length).toBeGreaterThan(0);
  });
});
