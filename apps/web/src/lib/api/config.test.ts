import { describe, it, expect } from "vitest";
import { getTargeting } from "@/lib/api/targeting";
import { getSkillsGap } from "@/lib/api/skills-gap";
import { GET as targetingRoute } from "@/app/api/targeting/route";

describe("lib/api config data-access", () => {
  it("getTargeting returns the targeting baseline", () => {
    const t = getTargeting();
    expect(t.roleTitles.length).toBeGreaterThan(0);
    expect(t.seniority.length).toBeGreaterThan(0);
  });

  it("getSkillsGap returns the skills-gap list", () => {
    const g = getSkillsGap();
    expect(g.length).toBeGreaterThan(0);
    expect(g[0]).toHaveProperty("roles");
    expect(g[0]).toHaveProperty("note");
  });

  it("the refactored /api/targeting route still returns the same shape", async () => {
    const body = await targetingRoute().json();
    expect(body.roleTitles).toEqual(getTargeting().roleTitles);
  });
});
