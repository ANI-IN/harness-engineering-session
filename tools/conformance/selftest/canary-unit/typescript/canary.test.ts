// First TypeScript test in the repository: unit-tests the canary's pure
// functions. The cross-stack behavior is covered by the conformance runner;
// this exists so the vitest gate (passWithNoTests: false) has real work.

import { describe, expect, it } from "vitest";
import { canary, render } from "./main";

const RAW = JSON.stringify({
  label: "canary",
  factors: [0.1, 0.2],
  segments: ["data", "notes", "first.md"],
});

describe("canary", () => {
  it("computes sum, path, and segment count", () => {
    const result = canary(RAW);
    expect(result.label).toBe("canary");
    expect(result.sum).toBe(0.30000000000000004);
    expect(result.path).toBe("data/notes/first.md");
    expect(result.segment_count).toBe(3);
  });

  it("render adds the deliberate cosmetic noise the normalizer must absorb", () => {
    const rendered = render(canary(RAW));
    expect(rendered.endsWith("\n")).toBe(true);
    const lines = rendered.trimEnd().split("\n");
    expect(lines.length).toBeGreaterThan(1);
    for (const line of lines.slice(0, -1)) {
      expect(line.endsWith("  ")).toBe(true);
    }
    expect(lines[0]?.startsWith("{")).toBe(true);
  });
});
