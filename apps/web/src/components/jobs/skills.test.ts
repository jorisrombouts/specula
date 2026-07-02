import { describe, it, expect } from "vitest";
import { candidateHas, splitSkills } from "@/components/jobs/skills";
import type { Candidate } from "@specula/shared-types";

const cand = {
  skills: ["Python", "PyTorch", "Distributed Systems"],
} as Candidate;

describe("skill matching", () => {
  it("candidateHas matches exact + substring (either direction)", () => {
    expect(candidateHas(cand, "Python")).toBe(true); // exact
    expect(candidateHas(cand, "PyTorch Lightning")).toBe(true); // target includes "pytorch"
    expect(candidateHas(cand, "Rust")).toBe(false);
  });

  it("splitSkills partitions required into have/miss covering all", () => {
    const { have, miss } = splitSkills(cand, ["Python", "Rust", "PyTorch"]);
    expect(have).toEqual(["Python", "PyTorch"]);
    expect(miss).toEqual(["Rust"]);
    expect([...have, ...miss].sort()).toEqual(
      ["Python", "PyTorch", "Rust"].sort(),
    );
  });
});
