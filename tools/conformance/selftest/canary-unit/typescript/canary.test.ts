// First TypeScript test in the repository: unit-tests the canary's pure
// functions. The cross-stack behavior is covered by the conformance runner;
// this exists so the vitest gate (passWithNoTests: false) has real work.

import { describe, expect, it } from "vitest";
import { canary, codePointLength, render } from "./main";

const RAW = JSON.stringify({
  label: "canary café ☕",
  factors: [0.1, 0.2],
  segments: ["data", "notes", "first.md"],
  tags: [],
  meta: {},
  parent: null,
  notes_file: new URL("../fixtures/notes.txt", import.meta.url).pathname,
});

describe("canary", () => {
  it("computes sum, path, and segment count", () => {
    const result = canary(RAW);
    expect(result.label).toBe("canary café ☕");
    expect(result.sum).toBe(0.30000000000000004);
    expect(result.path).toBe("data/notes/first.md");
    expect(result.segment_count).toBe(3);
    expect(result.tags).toEqual([]);
    expect(result.meta).toEqual({});
    expect(result.parent).toBeNull();
  });

  it("counts notes lines and words across CRLF, longest by code points", () => {
    const notes = canary(RAW).notes as {
      lines: number;
      words: { total: number; longest: { text: string; length: number } };
    };
    expect(notes.lines).toBe(3);
    expect(notes.words.total).toBe(9);
    expect(notes.words.longest.text).toBe("mega🚀rocket");
    expect(notes.words.longest.length).toBe(11);
  });

  it("counts code points, not UTF-16 units", () => {
    expect(codePointLength("mega🚀rocket")).toBe(11);
    expect("mega🚀rocket".length).toBe(12);
    expect(codePointLength("café")).toBe(4);
  });

  it("render adds the deliberate cosmetic noise the normalizer must absorb", () => {
    const rendered = render(canary(RAW));
    expect(rendered.endsWith("\n")).toBe(true);
    const lines = rendered.trimEnd().split("\n");
    expect(lines.length).toBeGreaterThan(1);
    for (const line of lines.slice(0, -1)) {
      expect(line.endsWith("  ")).toBe(true);
    }
    expect(rendered).toContain("☕");
  });
});
