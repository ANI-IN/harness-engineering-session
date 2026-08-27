// Project 03 TypeScript test suite: the chunking rule, staleness, the ask
// refusal, the continuity proof, the dogfood check, and the independent
// evidence contract. The continuity report here must match the pinned
// expectation byte-for-byte; the Python suite additionally asserts the
// child-process spawns directly, and cross-track byte equality carries
// that proof to this track.

import { spawnSync } from "node:child_process";
import { appendFileSync, copyFileSync, cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";

import {
  chunkText,
  cmdAsk,
  cmdIndex,
  cmdInit,
  cmdStatus,
  cmdWorkspaceCheck,
  extractMetadata,
  parseHandoff,
  runContinuity,
  splitCommand,
} from "../main";

const PROJECT_DIR = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const REPO_ROOT = dirname(dirname(PROJECT_DIR));
const MAIN_TS = join(PROJECT_DIR, "solution", "typescript", "main.ts");

const tempDirs: string[] = [];
function makeTempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "p03-test-"));
  tempDirs.push(dir);
  return dir;
}
afterEach(() => {
  while (tempDirs.length > 0) {
    rmSync(tempDirs.pop() as string, { recursive: true, force: true });
  }
});

function initializedDir(base: string): string {
  const dataDir = join(base, "kb-data");
  const seed = join(PROJECT_DIR, "fixtures", "kb-data", "documents");
  const [exitCode] = cmdInit(dataDir, seed);
  expect(exitCode).toBe(0);
  return dataDir;
}

describe("chunking", () => {
  it("packs paragraphs up to the limit", () => {
    const chunks = chunkText("aaa\n\nbbb\n\nccc\n");
    expect(chunks).toHaveLength(1);
    expect(chunks[0]?.text).toBe("aaa\n\nbbb\n\nccc");
  });

  it("flushes at the boundary", () => {
    const text = "x".repeat(300) + "\n\n" + "y".repeat(300) + "\n\n" + "z".repeat(100);
    const chunks = chunkText(text);
    expect(chunks.map((chunk) => chunk.text[0])).toEqual(["x", "y"]);
    expect(chunks[1]?.text.endsWith("z".repeat(100))).toBe(true);
  });

  it("keeps an oversized paragraph whole", () => {
    const text = "short\n\n" + "w ".repeat(400).trim() + "\n\nshort again\n";
    const chunks = chunkText(text);
    expect(chunks).toHaveLength(3);
    expect(chunks[1]?.words).toBe(400);
  });

  it("counts chunk metadata", () => {
    const chunks = chunkText("one two three\n");
    expect(chunks[0]?.chars).toBe(13);
    expect(chunks[0]?.words).toBe(3);
  });

  it("extracts document metadata", () => {
    expect(extractMetadata("a b\n\nc d e\n")).toEqual({ chars: 11, words: 5, paragraphs: 2 });
  });
});

describe("index and status", () => {
  it("reaches ready after indexing", () => {
    const dataDir = initializedDir(makeTempDir());
    expect(cmdIndex(dataDir)[0]).toBe(0);
    const status = JSON.parse(cmdStatus(dataDir)[1]) as { state: string; indexed: number };
    expect(status.state).toBe("ready");
    expect(status.indexed).toBe(3);
  });

  it("marks an edited document stale and reindexes only it", () => {
    const dataDir = initializedDir(makeTempDir());
    cmdIndex(dataDir);
    appendFileSync(join(dataDir, "documents", "team-meeting.txt"), "\nA new line.\n", "utf8");
    const status = JSON.parse(cmdStatus(dataDir)[1]) as { state: string; stale: string[] };
    expect(status.state).toBe("stale");
    expect(status.stale).toEqual(["team-meeting"]);
    const report = JSON.parse(cmdIndex(dataDir)[1]) as { indexed: Array<{ document: string }> };
    expect(report.indexed.map((item) => item.document)).toEqual(["team-meeting"]);
    expect((JSON.parse(cmdStatus(dataDir)[1]) as { state: string }).state).toBe("ready");
  });

  it("refuses ask until the index is ready, then cites chunks", () => {
    const dataDir = initializedDir(makeTempDir());
    const [exitCode, out, err] = cmdAsk(dataDir, "ranking citations");
    expect([exitCode, out]).toEqual([1, ""]);
    expect(err).toContain("index not ready");
    cmdIndex(dataDir);
    const [okCode, okOut] = cmdAsk(dataDir, "Which lines become citations in the ranking?");
    expect(okCode).toBe(0);
    const citations = (JSON.parse(okOut) as { citations: Array<{ chunk: number }> }).citations;
    expect(citations.length).toBeGreaterThan(0);
    expect(citations.every((citation) => typeof citation.chunk === "number")).toBe(true);
  });
});

describe("continuity", () => {
  it(
    "resumes from disk alone across the two-session process chain",
    () => {
      const work = join(makeTempDir(), "work");
      const [exitCode, out] = runContinuity(work);
      expect(exitCode).toBe(0);
      const report = JSON.parse(out) as {
        session_a: { steps: Array<{ exit: number }> };
        session_b: { handoff_sections: number; steps: Array<{ exit: number }> };
        resume: { resumed: boolean; status_matches_session_a: boolean };
      };
      expect(report.resume.resumed).toBe(true);
      expect(report.resume.status_matches_session_a).toBe(true);
      expect(report.session_a.steps).toHaveLength(4);
      expect(report.session_b.steps).toHaveLength(3);
      expect(report.session_b.handoff_sections).toBe(3);
    },
    240000,
  );

  it("matches the pinned continuity expectation", () => {
    const work = join(makeTempDir(), "work");
    const [, out] = runContinuity(work);
    const pinned = readFileSync(join(PROJECT_DIR, "expected", "continuity.json"), "utf8");
    expect(JSON.parse(out)).toEqual(JSON.parse(pinned));
  }, 240000);
});

describe("dogfood", () => {
  it("committed harness passes its own doctor", () => {
    const [exitCode, out] = cmdWorkspaceCheck(join(PROJECT_DIR, "harness"));
    expect(exitCode).toBe(0);
    expect((JSON.parse(out) as { ready: boolean }).ready).toBe(true);
  });

  it("handoff parses with required sections", () => {
    const text = readFileSync(join(PROJECT_DIR, "harness", "session-handoff.md"), "utf8");
    const headings = parseHandoff(text).sections.map((section) => section.heading);
    for (const required of ["Verified now", "Broken or unverified", "Next best step"]) {
      expect(headings).toContain(required);
    }
  });
});

function expandKb(command: string): string[] {
  const tokens = splitCommand(command);
  expect(tokens[0]).toBe("kb");
  return [join(REPO_ROOT, "node_modules", ".bin", "tsx"), MAIN_TS, ...tokens.slice(1)];
}

// Every evidence command in the committed feature list executed through the
// real CLI as a subprocess, in feature-list order, in a fresh workspace;
// output must equal the recorded `observed` string.
describe("independent evidence", () => {
  it(
    "reproduces each feature's observed output through the real CLI",
    () => {
      const dir = makeTempDir();
      cpSync(join(PROJECT_DIR, "fixtures", "kb-data", "documents"), join(dir, "data", "sample-documents"), {
        recursive: true,
      });
      mkdirSync(join(dir, "imports"));
      copyFileSync(
        join(PROJECT_DIR, "fixtures", "imports", "field-guide.md"),
        join(dir, "imports", "field-guide.md"),
      );
      const committed = JSON.parse(
        readFileSync(join(PROJECT_DIR, "harness", "feature_list.json"), "utf8"),
      ) as { features: Array<{ id: string; evidence?: { command: string; observed: string } }> };
      for (const feature of committed.features) {
        const evidence = feature.evidence;
        expect(evidence, feature.id).toBeDefined();
        if (evidence === undefined) {
          continue;
        }
        const [cli, ...args] = expandKb(evidence.command);
        const proc = spawnSync(cli as string, args, { cwd: dir, encoding: "utf8", timeout: 300000 });
        const observed = proc.stdout
          ? `exit ${proc.status}: ${JSON.stringify(JSON.parse(proc.stdout))}`
          : `exit ${proc.status}: ${proc.stderr.trim()}`;
        expect(observed, feature.id).toBe(evidence.observed);
      }
    },
    600000,
  );
});
