import { describe, it, expect, vi } from "vitest";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getApprovals } = await import("@/lib/api/approvals");
const { getCompanies } = await import("@/lib/api/companies");
const { getInsights } = await import("@/lib/api/insights");
const { GET: approvalsRoute } = await import("@/app/api/approvals/route");
const { GET: companiesRoute } = await import("@/app/api/companies/route");
const { GET: insightsRoute } = await import("@/app/api/insights/route");

describe("lib/api read-view data-access", () => {
  it("getApprovals returns the 6-approval queue", async () => {
    const a = await getApprovals();
    expect(a).toHaveLength(6);
    expect(a.find((x) => x.id === "a5")?.unverified).toBe(true);
  });

  it("getCompanies returns the 10-company registry", async () => {
    const c = await getCompanies();
    expect(c).toHaveLength(10);
    expect(c.find((x) => x.name === "Sereact")?.conf).toBe(64);
  });

  it("getInsights returns the insights aggregate", async () => {
    const i = await getInsights();
    expect(i.totalAnalysed).toBe(312);
    expect(i.lowConfExcluded).toBe(24);
    expect(i.skillDemand).toHaveLength(7);
  });

  it("the routes forward the same shapes", async () => {
    expect(await (await approvalsRoute()).json()).toHaveLength(6);
    expect(await (await companiesRoute()).json()).toHaveLength(10);
    expect((await (await insightsRoute()).json()).totalAnalysed).toBe(312);
  });
});
