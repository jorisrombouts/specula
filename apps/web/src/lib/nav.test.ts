import { describe, it, expect } from "vitest";
import { NAV, isActive, type NavItem } from "@/lib/nav";

const items = NAV.filter((e): e is NavItem => "id" in e);

describe("NAV model", () => {
  it("has the six sidebar nav items in order", () => {
    expect(items.map((i) => i.id)).toEqual([
      "jobs",
      "approvals",
      "companies",
      "insights",
      "profiles",
      "targeting",
    ]);
  });

  it("groups items under the three section labels", () => {
    expect(
      NAV.filter((e) => "section" in e).map(
        (e) => (e as { section: string }).section,
      ),
    ).toEqual(["Pipeline", "Intelligence", "Configure"]);
  });

  it("maps each item to its own route", () => {
    expect(items.map((i) => i.href)).toEqual([
      "/jobs",
      "/approvals",
      "/companies",
      "/insights",
      "/profiles",
      "/targeting",
    ]);
  });
});

describe("isActive", () => {
  it("matches the exact route", () => {
    expect(isActive("/jobs", "/jobs")).toBe(true);
  });
  it("does not match a different route", () => {
    expect(isActive("/jobs", "/companies")).toBe(false);
  });
  it("matches nested paths under the route", () => {
    expect(isActive("/jobs", "/jobs/abc")).toBe(true);
  });
});
