import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MatchMeter, matchColor } from "@/components/atoms/match-meter";
import type { Job } from "@specula/shared-types";

afterEach(cleanup);

const base = {
  id: "t1",
  company: "X",
  logo: "X",
  title: "T",
  city: "C",
  country: "NL",
  hq: "NL",
  mode: "Remote",
  flag: "🇳🇱",
  match: 90,
  factors: { role: 96, skill: 89, loc: 92 },
  overlap: [8, 9],
  seniority: "Senior",
  edu: "MSc",
  deadlineDays: 9,
  salary: null,
  posted: "1d ago",
  status: null,
  isNew: true,
  stillOpen: true,
  originVerified: true,
  hqConf: 98,
  stack: [],
  niceToHave: [],
  visa: "",
  langs: [],
  contract: "",
  geo: "",
  confidence: 90,
  responsibilities: [],
  summary: "",
  rationale: "",
} as unknown as Job;

describe("matchColor", () => {
  it("warn when redFlag", () => {
    expect(matchColor({ ...base, redFlag: "x" })).toBe("text-warn");
  });
  it("accent when match >= 85 and no red flag", () => {
    expect(matchColor({ ...base, match: 90 })).toBe("text-accent");
  });
  it("ink otherwise", () => {
    expect(matchColor({ ...base, match: 70 })).toBe("text-ink");
  });
});

describe("MatchMeter", () => {
  it("bars style shows the match number and ROLE/SKILL/LOC", () => {
    render(<MatchMeter job={base} mstyle="bars" />);
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.getByText("ROLE")).toBeInTheDocument();
    expect(screen.getByText("SKILL")).toBeInTheDocument();
    expect(screen.getByText("LOC")).toBeInTheDocument();
  });
  it("figure style shows the number without the factor rows", () => {
    render(<MatchMeter job={base} mstyle="figure" />);
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.queryByText("ROLE")).toBeNull();
  });
  it("shows the final match number immediately under reduced motion (no count-up)", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: true, // prefers-reduced-motion: reduce
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    render(<MatchMeter job={base} mstyle="bars" countUp replay="x" />);
    expect(screen.getByText("90")).toBeInTheDocument();
  });
});
