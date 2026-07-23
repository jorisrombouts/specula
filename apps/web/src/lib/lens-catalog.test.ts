import { describe, it, expect } from "vitest";
import { parseScope, serializeScope, originLabel } from "@/lib/lens-catalog";

describe("lens-catalog scope helpers", () => {
  it("parseScope classifies each scope form (region before country)", () => {
    expect(parseScope("")).toEqual({ type: "Any", value: "" });
    expect(parseScope("EU")).toEqual({ type: "Region", value: "EU" }); // region, not country
    expect(parseScope("ES")).toEqual({ type: "Country", value: "ES" });
    expect(parseScope("Berlin, DE")).toEqual({
      type: "City",
      value: "Berlin, DE",
    });
  });
  it("serializeScope is the inverse (Any -> empty)", () => {
    expect(serializeScope({ type: "Any", value: "" })).toBe("");
    expect(serializeScope({ type: "Country", value: "ES" })).toBe("ES");
    expect(serializeScope(parseScope("EU"))).toBe("EU");
  });
  it("originLabel maps values, unknown -> Any HQ", () => {
    expect(originLabel("foreign_hq")).toBe("Only foreign HQ");
    expect(originLabel("domestic_hq")).toBe("Only domestic HQ");
    expect(originLabel("")).toBe("Any HQ");
    expect(originLabel("whatever")).toBe("Any HQ");
  });
});
