// Project 02 TypeScript test suite: metadata persistence, the workspace
// doctor's three rules in isolation, the dogfood check, and the independent
// evidence contract.

import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";

import {
  checkFeatureEvidence,
  checkRouterTargets,
  checkSessionHandoff,
  cmdImport,
  cmdInit,
  cmdList,
  cmdShow,
  cmdWorkspaceCheck,
  extractTitle,
  parseHandoff,
} from "../main";

const PROJECT_DIR = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const REPO_ROOT = dirname(dirname(PROJECT_DIR));
const MAIN_TS = join(PROJECT_DIR, "solution", "typescript", "main.ts");

const tempDirs: string[] = [];
function makeTempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "p02-test-"));
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

describe("metadata persistence", () => {
  it("import survives a fresh process", () => {
    const dataDir = initializedDir(makeTempDir());
    const source = join(PROJECT_DIR, "fixtures", "imports", "field-guide.md");
    const [exitCode, out] = cmdImport(dataDir, [source]);
    expect(exitCode).toBe(0);
    expect((JSON.parse(out) as { imported: Array<{ origin: string }> }).imported[0]?.origin).toBe(
      "imported",
    );
    const proc = spawnSync(
      join(REPO_ROOT, "node_modules", ".bin", "tsx"),
      [MAIN_TS, "list", "--data-dir", dataDir],
      { encoding: "utf8", timeout: 120000 },
    );
    const listing = JSON.parse(proc.stdout) as { documents: Array<{ id: string }> };
    expect(listing.documents.map((doc) => doc.id)).toEqual([
      "architecture-notes", "field-guide", "retrieval-plan", "team-meeting",
    ]);
  });

  it("skips a duplicate import instead of duplicating", () => {
    const dataDir = initializedDir(makeTempDir());
    const duplicate = join(PROJECT_DIR, "fixtures", "kb-data", "documents", "team-meeting.txt");
    const [, out] = cmdImport(dataDir, [duplicate]);
    const report = JSON.parse(out) as { imported: unknown[]; skipped: unknown[] };
    expect(report.imported).toEqual([]);
    expect(report.skipped).toEqual([{ filename: "team-meeting.txt", reason: "already-imported" }]);
  });

  it("requires the index, not just files", () => {
    const dataDir = initializedDir(makeTempDir());
    unlinkSync(join(dataDir, "index", "documents-meta.json"));
    const [exitCode, out, err] = cmdList(dataDir);
    expect([exitCode, out]).toEqual([1, ""]);
    expect(err).toContain("metadata index missing");
  });

  it("show returns the entry plus content", () => {
    const dataDir = initializedDir(makeTempDir());
    const [, out] = cmdShow(dataDir, "retrieval-plan");
    const payload = JSON.parse(out) as { origin: string; content: string };
    expect(payload.origin).toBe("seeded");
    expect(payload.content.startsWith("# Retrieval plan")).toBe(true);
  });

  it("extractTitle falls back to the filename", () => {
    expect(extractTitle("no heading here\n", "notes.txt")).toBe("notes.txt");
    expect(extractTitle("# Real title\nbody\n", "notes.txt")).toBe("Real title");
  });
});

describe("workspace doctor", () => {
  function makeReady(): string {
    const base = makeTempDir();
    cpSync(join(PROJECT_DIR, "fixtures", "workspaces", "workspace-ready"), join(base, "ws"), {
      recursive: true,
    });
    return join(base, "ws");
  }

  it("passes the ready fixture", () => {
    const [exitCode, out] = cmdWorkspaceCheck(makeReady());
    expect(exitCode).toBe(0);
    expect((JSON.parse(out) as { ready: boolean }).ready).toBe(true);
  });

  it("catches a router defect alone", () => {
    const workspace = makeReady();
    const agents = join(workspace, "AGENTS.md");
    writeFileSync(
      agents,
      readFileSync(agents, "utf8") + "\n- Ghost doc: [docs/GHOST.md](docs/GHOST.md)\n",
      "utf8",
    );
    const check = checkRouterTargets(workspace);
    expect(check.passed).toBe(false);
    expect(check.detail).toContain("docs/GHOST.md");
  });

  it("catches a handoff defect alone", () => {
    const workspace = makeReady();
    const handoff = join(workspace, "session-handoff.md");
    writeFileSync(
      handoff,
      readFileSync(handoff, "utf8").replace("## Next best step", "## Notes"),
      "utf8",
    );
    const check = checkSessionHandoff(workspace);
    expect(check.passed).toBe(false);
    expect(check.detail).toContain("Next best step");
  });

  it("catches an evidence defect alone", () => {
    const workspace = makeReady();
    const featurePath = join(workspace, "feature_list.json");
    const featureList = JSON.parse(readFileSync(featurePath, "utf8")) as {
      features: Array<{ evidence?: unknown }>;
    };
    delete featureList.features[0]?.evidence;
    writeFileSync(featurePath, JSON.stringify(featureList, null, 2), "utf8");
    const check = checkFeatureEvidence(workspace);
    expect(check.passed).toBe(false);
    expect(check.detail).toContain("passing without evidence");
  });

  it("keeps every handoff section in order when parsing", () => {
    const text = readFileSync(join(PROJECT_DIR, "harness", "session-handoff.md"), "utf8");
    const document = parseHandoff(text);
    expect(document.sections.map((section) => section.heading)).toEqual([
      "Verified now", "Changed this session", "Broken or unverified",
      "Next best step", "Commands",
    ]);
  });

  it("dogfood: the committed harness passes its own doctor", () => {
    const [exitCode, out] = cmdWorkspaceCheck(join(PROJECT_DIR, "harness"));
    expect(exitCode).toBe(0);
    const report = JSON.parse(out) as { ready: boolean; checks: Array<{ id: string }> };
    expect(report.ready).toBe(true);
    expect(report.checks.map((check) => check.id)).toEqual([
      "router-targets", "session-handoff", "feature-evidence",
    ]);
  });
});

// Expand the canonical `kb ...` form to this track's real CLI.
function expandKb(command: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let inQuotes = false;
  for (const char of command) {
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === " " && !inQuotes) {
      if (current) {
        tokens.push(current);
        current = "";
      }
    } else {
      current += char;
    }
  }
  if (current) {
    tokens.push(current);
  }
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
        const proc = spawnSync(cli as string, args, { cwd: dir, encoding: "utf8", timeout: 120000 });
        const observed = proc.stdout
          ? `exit ${proc.status}: ${JSON.stringify(JSON.parse(proc.stdout))}`
          : `exit ${proc.status}: ${proc.stderr.trim()}`;
        expect(observed, feature.id).toBe(evidence.observed);
      }
    },
    240000,
  );
});
