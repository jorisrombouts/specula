import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { InsightsView } from "@/components/insights/insights-view";
import { DemandTrend } from "@/components/insights/demand-trend";
import { getInsights } from "@/lib/api/insights";

afterEach(cleanup);
const insights = getInsights();

describe("InsightsView", () => {
  it("renders the low-confidence exclusion banner with the excluded count", () => {
    render(<InsightsView insights={insights} />);
    expect(
      screen.getByText(
        /24 low-confidence extractions excluded from every aggregate/,
      ),
    ).toBeInTheDocument();
  });

  it("renders the analysed total at its final value", () => {
    const { container } = render(<InsightsView insights={insights} />);
    expect(container.querySelector("header")).toHaveTextContent("312");
  });

  it("renders all six panels", () => {
    render(<InsightsView insights={insights} />);
    for (const title of [
      "Skill demand",
      "Demand drift",
      "Seniority mix",
      "Work-mode mix",
      "Salary distribution",
      "Most-active companies",
    ]) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  it("marks a gap skill and shows the salary display-only caption", () => {
    render(<InsightsView insights={insights} />);
    // Kubernetes has gap: true
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getAllByText("gap").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Never used to rank or filter/),
    ).toBeInTheDocument();
  });
});

describe("DemandTrend", () => {
  it("renders a column per week and a legend entry per series", () => {
    const { container } = render(<DemandTrend trend={insights.trend} />);
    expect(container.querySelectorAll("[data-trend-col]")).toHaveLength(8);
    // legend: one entry per series (3)
    expect(screen.getByText("LLM / RAG")).toBeInTheDocument();
    expect(screen.getByText("Inference / vLLM")).toBeInTheDocument();
  });
});
