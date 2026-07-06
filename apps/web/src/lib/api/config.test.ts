import { describe, it, expect, vi } from "vitest";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getTargeting } = await import("@/lib/api/targeting");
const { getSkillsGap } = await import("@/lib/api/skills-gap");
const { getTweaks, putTweaks } = await import("@/lib/api/tweaks");
const { GET: targetingRoute } = await import("@/app/api/targeting/route");
const { GET: tweaksRoute, PUT: tweaksPutRoute } =
  await import("@/app/api/tweaks/route");
const { TWEAK_DEFAULTS } = await import("@/lib/tweaks-init");

describe("lib/api config data-access", () => {
  it("getTargeting returns the targeting baseline", async () => {
    const t = await getTargeting();
    expect(t.roleTitles.length).toBeGreaterThan(0);
    expect(t.seniority.length).toBeGreaterThan(0);
  });

  it("getSkillsGap returns the skills-gap list", async () => {
    const g = await getSkillsGap();
    expect(g.length).toBeGreaterThan(0);
    expect(g[0]).toHaveProperty("roles");
    expect(g[0]).toHaveProperty("note");
  });

  it("the /api/targeting route forwards the same shape", async () => {
    const body = await (await targetingRoute()).json();
    expect(body.roleTitles).toEqual((await getTargeting()).roleTitles);
  });

  it("getTweaks returns the stored tweaks", async () => {
    expect(await getTweaks()).toEqual(TWEAK_DEFAULTS);
  });

  it("putTweaks persists and returns the saved tweaks", async () => {
    const next = { ...TWEAK_DEFAULTS, mstyle: "ring" as const };
    expect(await putTweaks(next)).toEqual(next);
  });

  it("the /api/tweaks route GETs the stored value and PUTs through the update", async () => {
    const getBody = await (await tweaksRoute()).json();
    expect(getBody).toEqual(TWEAK_DEFAULTS);

    const next = { ...TWEAK_DEFAULTS, layout: "cards" };
    const putBody = await (
      await tweaksPutRoute(
        new Request("http://x/api/tweaks", {
          method: "PUT",
          body: JSON.stringify(next),
        }),
      )
    ).json();
    expect(putBody).toEqual(next);
  });
});
