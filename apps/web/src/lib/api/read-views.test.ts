import { describe, it, expect } from "vitest";
import { getApprovals } from "@/lib/api/approvals";
import { getCompanies } from "@/lib/api/companies";
import { getInsights } from "@/lib/api/insights";
import { GET as approvalsRoute } from "@/app/api/approvals/route";
import { GET as companiesRoute } from "@/app/api/companies/route";
import { GET as insightsRoute } from "@/app/api/insights/route";

describe("lib/api read-view data-access", () => {
  it("getApprovals returns the 6-approval queue", () => {
    const a = getApprovals();
    expect(a).toHaveLength(6);
    expect(a.find((x) => x.id === "a5")?.unverified).toBe(true);
  });

  it("getCompanies returns the 10-company registry", () => {
    const c = getCompanies();
    expect(c).toHaveLength(10);
    expect(c.find((x) => x.name === "Sereact")?.conf).toBe(64);
  });

  it("getInsights returns the insights aggregate", () => {
    const i = getInsights();
    expect(i.totalAnalysed).toBe(312);
    expect(i.lowConfExcluded).toBe(24);
    expect(i.skillDemand).toHaveLength(7);
  });

  it("the refactored routes still return the same shapes", async () => {
    expect(await approvalsRoute().json()).toHaveLength(6);
    expect(await companiesRoute().json()).toHaveLength(10);
    expect((await insightsRoute().json()).totalAnalysed).toBe(312);
  });
});
