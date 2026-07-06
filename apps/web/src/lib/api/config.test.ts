import { describe, it, expect } from "vitest";
import { getTargeting } from "@/lib/api/targeting";
import { getSkillsGap } from "@/lib/api/skills-gap";
import { getTweaks, putTweaks } from "@/lib/api/tweaks";
import { GET as targetingRoute } from "@/app/api/targeting/route";
import {
  GET as tweaksRoute,
  PUT as tweaksPutRoute,
} from "@/app/api/tweaks/route";
import { TWEAK_DEFAULTS } from "@/lib/tweaks-init";

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

  it("getTweaks returns the tweak defaults", () => {
    expect(getTweaks()).toEqual(TWEAK_DEFAULTS);
  });

  it("putTweaks echoes the validated tweaks", () => {
    const next = { ...TWEAK_DEFAULTS, mstyle: "ring" as const };
    expect(putTweaks(next)).toEqual(next);
  });

  it("the /api/tweaks route GETs defaults and PUTs an echo", async () => {
    const getBody = await tweaksRoute().json();
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
